"""Read-only, fail-closed validation of the unreleased A-21B admission schema.

No table/index repair and no row updates. CHECKs are compared as a small boolean
expression tree, not by their names or by removing meaningful parentheses.
Unsupported expressions require administrative review rather than guessing.
"""

import re

from sqlalchemy import Boolean, DateTime, Integer, String, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError


TABLE = "external_review_import_attempts"
# Frozen schema contract: future changes require an explicit compatibility decision.
CHECKS = (
    "reserved_requests BETWEEN 1 AND 5",
    "active IS NULL OR active = true",
    "(state = 'running' AND active IS NOT NULL) OR "
    "(state = 'unknown' AND active IS NOT NULL) OR (state = 'finished' AND active IS NULL)",
)
_TOKEN = re.compile(r"\s*(::|>=|<=|<>|!=|[()=<>]|-?\d+|'(?:''|[^'])*'|\"[A-Za-z_][A-Za-z_0-9]*\"|[A-Za-z_][A-Za-z_0-9]*)")


class ExternalImportSchemaError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("El esquema de admisión externa es incompatible; requiere revisión administrativa")


def _check_signature(sql: str) -> tuple:
    """Recognize only the finite grammar used by these three CHECK definitions.

    Accept redundant parentheses, reordered AND/OR, BETWEEN expanded by PG,
    and PG's lossless text casts. Preserve literals, types and AND/OR precedence.
    Never execute a reflected CHECK expression or accept arbitrary SQL.
    """
    if type(sql) is not str or len(sql) > 4096:
        raise ValueError("Unsupported CHECK")
    tokens = []
    offset = 0
    while offset < len(sql.rstrip()):
        match = _TOKEN.match(sql, offset)
        if match is None:
            raise ValueError("Unsupported CHECK")
        value = match.group(1)
        tokens.append(value if value.startswith(("'", '"')) else value.lower())
        offset = match.end()
    index = 0

    def take(value):
        nonlocal index
        if index < len(tokens) and tokens[index] == value:
            index += 1
            return True
        return False

    def require(value):
        if not take(value):
            raise ValueError("Unsupported CHECK")

    def combine(operator, *values):
        children = []
        for value in values:
            children.extend(value[1:] if value[0] == operator else (value,))
        return (operator, *sorted(children, key=repr))

    def atom():
        nonlocal index
        if take("("):
            value = expression()
            require(")")
        elif index < len(tokens):
            token = tokens[index]
            index += 1
            if token.startswith("'"):
                value = ("text", token[1:-1].replace("''", "'"))
            elif re.fullmatch(r"-?\d+", token):
                value = ("number", int(token))
            elif token in ("true", "false", "null"):
                value = ("literal", token)
            elif token.strip('"') in ("reserved_requests", "active", "state"):
                value = ("column", token.strip('"'))
            else:
                raise ValueError("Unsupported CHECK")
        else:
            raise ValueError("Unsupported CHECK")
        while take("::"):
            if value[0] not in ("column", "text"):
                raise ValueError("Unsupported cast")
            if take("character"):
                require("varying")
            elif not take("text") and not take("varchar"):
                raise ValueError("Unsupported cast")
            # No varchar(n): it can truncate values and change CHECK semantics.
        return value

    def comparison():
        nonlocal index
        left = atom()
        if take("is"):
            negative = take("not")
            require("null")
            return ("is_not_null" if negative else "is_null", left)
        if take("between"):
            lower = atom()
            require("and")
            return combine("and", (">=", left, lower), ("<=", left, atom()))
        if index < len(tokens) and tokens[index] in ("=", ">=", "<=", "<", ">", "!=", "<>"):
            operator = tokens[index]
            index += 1
            right = atom()
            if operator == "=":
                # SQLite TRUE is 1 only with the exact, validated column set.
                # PG's reflected native boolean stays TRUE.
                if left == ("column", "active") and right == ("number", 1):
                    right = ("literal", "true")
                return (operator, *sorted((left, right), key=repr))
            return (operator, left, right)
        return left

    def conjunction():
        value = comparison()
        while take("and"):
            value = combine("and", value, comparison())
        return value

    def expression():
        value = conjunction()
        while take("or"):
            value = combine("or", value, conjunction())
        return value

    result = expression()
    if index != len(tokens):
        raise ValueError("Unsupported CHECK")
    return result


def _verify(connection: Connection) -> None:
    dialect = connection.dialect.name
    if dialect not in ("sqlite", "postgresql"):
        raise ExternalImportSchemaError()
    inspector = inspect(connection)
    definitions = {
        "operation_id": (String, 36), "tenant_id": (Integer, None),
        "source": (String, 100), "business_data_id": (String, 128),
        "started_at": (DateTime, None), "reserved_requests": (Integer, None),
        "active": (Boolean, None), "state": (String, 16),
    }
    columns = {column["name"]: column for column in inspector.get_columns(TABLE)}
    # Closed contract: even "true"/"false" may be SQLite column references,
    # changing the meaning of an otherwise identical reflected CHECK.
    if definitions.keys() != columns.keys():
        raise ExternalImportSchemaError()
    for name, (kind, length) in definitions.items():
        column = columns[name]
        if (not isinstance(column["type"], kind) or column["nullable"] != (name == "active")
                or (length is not None and column["type"].length != length)
                or (name == "started_at" and column["type"].timezone)):
            raise ExternalImportSchemaError()
    if inspector.get_pk_constraint(TABLE)["constrained_columns"] != ["operation_id"]:
        raise ExternalImportSchemaError()
    scope = ["tenant_id", "source", "business_data_id"]
    foreign = inspector.get_foreign_keys(TABLE)
    if not any(
        item["constrained_columns"] == scope and item["referred_columns"] == scope
        and item["referred_table"] == "external_review_connections"
        and item.get("referred_schema") in (None, inspector.default_schema_name)
        and all((item.get("options") or {}).get(key) in (None, "NO ACTION", "RESTRICT") for key in ("ondelete", "onupdate"))
        and not (item.get("options") or {}).get("deferrable")
        for item in foreign
    ):
        raise ExternalImportSchemaError()
    unique = inspector.get_unique_constraints(TABLE)
    if not any(item["column_names"] == [*scope, "active"]
               and not (item.get("dialect_options") or {}).get("postgresql_nulls_not_distinct")
               for item in unique):
        raise ExternalImportSchemaError()
    required = {_check_signature(sql) for sql in CHECKS}
    reflected = {_check_signature(item["sqltext"]) for item in inspector.get_check_constraints(TABLE)}
    if not required <= reflected:
        raise ExternalImportSchemaError()
    if dialect == "sqlite":
        if connection.exec_driver_sql("PRAGMA ignore_check_constraints").scalar_one() != 0:
            raise ExternalImportSchemaError()
        ddl = connection.execute(text(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=:table"
        ), {"table": TABLE}).scalar_one()
        # Reflection omits SQLite column collations. Accept only default/BINARY;
        # reject unknown spellings too, rather than assuming CHECK equality is exact.
        without_binary = re.sub(r'\bcollate\s+(?:"binary"|binary\b)', '', ddl, flags=re.IGNORECASE)
        if re.search(r'\bcollate\b', without_binary, flags=re.IGNORECASE):
            raise ExternalImportSchemaError()
        complete_binary_key = False
        for index in connection.exec_driver_sql(f'PRAGMA index_list("{TABLE}")').mappings():
            if not index["unique"] or index["partial"]:
                continue
            quoted = connection.dialect.identifier_preparer.quote_identifier(index["name"])
            keys = [row for row in connection.exec_driver_sql(f"PRAGMA index_xinfo({quoted})").mappings() if row["key"]]
            if ([row["name"] for row in keys] == [*scope, "active"]
                    and all(row["coll"] == "BINARY" for row in keys)):
                complete_binary_key = True
        if not complete_binary_key or connection.exec_driver_sql(
            f"SELECT EXISTS (SELECT 1 FROM pragma_foreign_key_check('{TABLE}'))"
        ).scalar_one():
            raise ExternalImportSchemaError()
    else:
        collations = connection.execute(text(
            "SELECT a.attname, co.collname FROM pg_attribute a "
            "JOIN pg_collation co ON co.oid=a.attcollation "
            "WHERE a.attrelid=to_regclass(:table) AND a.attname IN ('source','business_data_id','state')"
        ), {"table": TABLE}).all()
        if len(collations) != 3 or any(row.collname != "C" for row in collations):
            raise ExternalImportSchemaError()
        # to_jsonb handles conenforced when present, without requiring PG 18+.
        constraints = connection.execute(text(
            "SELECT c.convalidated, c.condeferrable, COALESCE(i.indisvalid, true) AS index_valid, "
            "COALESCE((to_jsonb(c)->>'conenforced')::boolean, true) AS enforced "
            "FROM pg_constraint c LEFT JOIN pg_index i ON i.indexrelid=c.conindid "
            "WHERE c.conrelid=to_regclass(:table) AND c.contype IN ('p','u','f','c')"
        ), {"table": TABLE}).mappings().all()
        if not constraints or any(not row["convalidated"] or row["condeferrable"]
                                  or not row["index_valid"] or not row["enforced"] for row in constraints):
            raise ExternalImportSchemaError()
    # Detect existing bad rows even after constraints were temporarily bypassed.
    # Do not resolve SQLite boolean names in row predicates either.
    active_literal = "1" if dialect == "sqlite" else "true"
    false_literal = "0" if dialect == "sqlite" else "false"
    row_checks = (CHECKS[0], f"active IS NULL OR active = {active_literal}", CHECKS[2])
    conditions = " AND ".join(f"({sql})" for sql in row_checks)
    invalid_type = " OR typeof(reserved_requests) <> 'integer'" if dialect == "sqlite" else ""
    if connection.exec_driver_sql(
        f"SELECT EXISTS (SELECT 1 FROM {TABLE} WHERE NOT COALESCE(({conditions}), {false_literal}){invalid_type})"
    ).scalar_one():
        raise ExternalImportSchemaError()
    if connection.exec_driver_sql(
        f"SELECT EXISTS (SELECT 1 FROM {TABLE} a LEFT JOIN external_review_connections c "
        "ON c.tenant_id=a.tenant_id AND c.source=a.source AND c.business_data_id=a.business_data_id "
        "WHERE c.tenant_id IS NULL)"
    ).scalar_one():
        raise ExternalImportSchemaError()


def verify_external_import_schema(connection: Connection) -> None:
    try:
        _verify(connection)
    except (SQLAlchemyError, ValueError, KeyError, TypeError, AttributeError, NotImplementedError, RecursionError):
        # Never include reflected DDL, SQL parameters or row values in errors.
        raise ExternalImportSchemaError() from None
