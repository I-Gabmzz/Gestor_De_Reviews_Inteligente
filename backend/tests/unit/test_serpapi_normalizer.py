"""Pruebas sintéticas de #3833: sin cliente HTTP, credenciales ni base de datos."""

import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys

import pytest

from app.schemas.serpapi import SerpApiPage, SerpApiResult, SerpApiReview
from app.services.serpapi_normalizer import normalize_serpapi_result


BUSINESS = "0x123:0x456"
PRIVATE = "synthetic-private-marker"
BACKEND = Path(__file__).resolve().parents[2]


def row(**changes):
    return {
        "review_id": "synthetic-review-1", "source": "Google",
        "user": {"name": "Autor sintético"},
        "snippet": "Texto alternativo sintético",
        "extracted_snippet": {"original": "Texto original sintético"},
        "iso_date": "2026-11-02T13:01:32Z", "rating": 4,
        **changes,
    }


def batch(*pages, **flags):
    native_pages = tuple(
        SerpApiPage(number=number, http_status=200, search_status="Success",
                    reviews=tuple(SerpApiReview(data=data) for data in records))
        for number, records in enumerate(pages, start=1)
    )
    return SerpApiResult(
        pages=native_pages, place_info={"title": PRIVATE},
        first_page_metadata={"id": PRIVATE}, request_count=len(pages),
        record_count=sum(len(page.reviews) for page in native_pages),
        **{"stop_reason": "no_next_token", "incomplete": False, "limited": False, **flags},
    )


def normalize(*pages, business=BUSINESS, **flags):
    return normalize_serpapi_result(batch(*pages, **flags), business_data_id=business)


def assert_reconciled(result):
    counts = result.counts
    assert counts.total == counts.with_text + counts.without_text + counts.rejected + counts.duplicates
    assert counts.conflicting <= counts.rejected
    positions = [item.position.ordinal for item in (
        *result.with_text, *result.without_text, *result.rejected, *result.duplicates,
    )]
    assert sorted(positions) == list(range(1, counts.total + 1))
    assert len(set(positions)) == counts.total


def assert_rejected(result, field, code):
    assert not result.with_text and not result.without_text
    assert result.batch_error is None
    assert len(result.rejected) == 1
    issue, = result.rejected[0].issues
    assert (issue.field, issue.code) == (field, code)
    assert issue.position == result.rejected[0].position
    assert (issue.position.page, issue.position.index, issue.position.ordinal) == (1, 1, 1)
    assert_reconciled(result)


def test_complete_record_maps_fields_and_preserves_opaque_id():
    result = normalize([row(review_id="  Opaque-Id_Á  ", user={"name": "  Autor sintético  "})])
    review, = result.with_text
    assert review.external_review_id == "  Opaque-Id_Á  "
    assert review.identity == ("Google", BUSINESS, "  Opaque-Id_Á  ")
    assert review.source == "Google" and review.business_data_id == BUSINESS
    assert review.author == "Autor sintético"
    assert review.content == "Texto original sintético"
    assert review.content_field == "extracted_snippet.original"
    assert review.review_date == datetime(2026, 11, 2, 13, 1, 32, tzinfo=timezone.utc)
    assert type(review.rating) is int and review.rating == 4
    assert not result.warnings and not result.rejected and not result.batch_error
    assert_reconciled(result)


@pytest.mark.parametrize("value", [None, "", " \t\n"])
def test_textless_record_preserves_other_fields_and_warns(value):
    result = normalize([row(extracted_snippet={"original": value}, snippet=value)])
    review, = result.without_text
    assert review.content is None and review.content_field is None
    assert review.author == "Autor sintético" and review.rating == 4
    assert review.external_review_id == "synthetic-review-1"
    assert review.review_date.tzinfo is timezone.utc
    assert review.source == "Google" and review.business_data_id == BUSINESS
    assert [(issue.field, issue.code) for issue in result.warnings] == [("content", "missing_content")]
    assert not result.with_text and not result.rejected
    assert_reconciled(result)


def test_absent_text_fields_do_not_use_owner_response_or_translation():
    data = row(extracted_snippet={"translated": PRIVATE}, response={"snippet": PRIVATE})
    data.pop("snippet")
    result = normalize([data])
    assert result.without_text[0].content is None
    assert result.warnings[0].code == "missing_content"


@pytest.mark.parametrize("user", [None, {}, {"name": None}, {"name": ""}, {"name": " \n"}])
def test_author_missing_or_blank_is_optional_with_warning(user):
    result = normalize([row(user=user)])
    assert result.with_text[0].author is None
    assert [(issue.field, issue.code) for issue in result.warnings] == [("user.name", "missing_author")]
    assert not result.rejected


def test_absent_author_and_text_produce_two_warnings_but_one_record():
    data = row()
    for key in ("user", "snippet", "extracted_snippet"):
        data.pop(key)
    result = normalize([data])
    assert result.counts.without_text == 1 and result.counts.total == 1
    assert {issue.code for issue in result.warnings} == {"missing_author", "missing_content"}
    assert_reconciled(result)


@pytest.mark.parametrize("user", [[], PRIVATE, True, {"name": 7}, {"name": []}, {"name": {}}])
def test_invalid_author_types_are_rejected(user):
    assert_rejected(normalize([row(user=user)]), "user.name", "invalid_type")


def test_author_length_matches_model_boundary_after_trim():
    assert normalize([row(user={"name": " " + "a" * 255 + " "})]).with_text[0].author == "a" * 255
    assert_rejected(normalize([row(user={"name": "a" * 256})]), "user.name", "too_long")


@pytest.mark.parametrize("value,code", [
    (None, "required"), ("", "required"), (" \t", "required"),
    (1, "invalid_type"), (True, "invalid_type"), ([], "invalid_type"), ({}, "invalid_type"),
    ("\ud800", "invalid_unicode"),
])
def test_invalid_ids_are_not_replaced(value, code):
    assert_rejected(normalize([row(review_id=value, id="alternative", link=PRIVATE)]), "review_id", code)


def test_absent_id_does_not_fall_back_to_other_identifiers():
    data = row(id="synthetic-alternative", link=PRIVATE)
    data.pop("review_id")
    assert_rejected(normalize([data]), "review_id", "required")


@pytest.mark.parametrize("extracted", [None, {}, {"original": None}, {"original": " \t"}])
def test_snippet_fallback_and_trim(extracted):
    review, = normalize([row(extracted_snippet=extracted, snippet="  Alternativa sintética  ")]).with_text
    assert review.content == "Alternativa sintética" and review.content_field == "snippet"


@pytest.mark.parametrize("field,value,reported", [
    ("snippet", [], "snippet"), ("snippet", {}, "snippet"), ("snippet", 4, "snippet"),
    ("snippet", False, "snippet"), ("extracted_snippet", [], "extracted_snippet.original"),
    ("extracted_snippet", PRIVATE, "extracted_snippet.original"),
    ("extracted_snippet", {"original": {}}, "extracted_snippet.original"),
    ("extracted_snippet", {"original": []}, "extracted_snippet.original"),
    ("extracted_snippet", {"original": True}, "extracted_snippet.original"),
])
def test_malformed_content_is_not_stringified_or_hidden_by_fallback(field, value, reported):
    assert_rejected(normalize([row(**{field: value})]), reported, "invalid_type")


@pytest.mark.parametrize("changes,field", [
    ({"user": {"name": "\udfff"}}, "user.name"),
    ({"snippet": "\udfff"}, "snippet"),
    ({"extracted_snippet": {"original": "\ud800"}}, "extracted_snippet.original"),
    ({"iso_date": "\ud800"}, "iso_date"),
])
def test_invalid_unicode_is_safe(changes, field):
    assert_rejected(normalize([row(**changes)]), field, "invalid_unicode")


@pytest.mark.parametrize("value,expected", [
    ("2026-11-02T13:01:32Z", datetime(2026, 11, 2, 13, 1, 32, tzinfo=timezone.utc)),
    ("2026-11-02T06:01:32-07:00", datetime(2026, 11, 2, 13, 1, 32, tzinfo=timezone.utc)),
    ("2026-11-02T15:01:32+02:00", datetime(2026, 11, 2, 13, 1, 32, tzinfo=timezone.utc)),
    ("2026-11-02T00:01:32+02:00", datetime(2026, 11, 1, 22, 1, 32, tzinfo=timezone.utc)),
    ("2026-11-02T13:01:32.123456+00:00", datetime(2026, 11, 2, 13, 1, 32, 123456, tzinfo=timezone.utc)),
])
def test_iso_dates_normalize_to_utc(value, expected):
    date = normalize([row(iso_date=value)]).with_text[0].review_date
    assert date == expected and date.tzinfo is timezone.utc


@pytest.mark.parametrize("value,code", [
    (None, "required"), ("", "required"), (" \t", "required"),
    (True, "invalid_type"), (7, "invalid_type"), ({}, "invalid_type"), ([], "invalid_type"),
    ("2026-11-02T13:01:32", "timezone_required"), ("2026-11-02", "timezone_required"),
    ("hace dos semanas", "invalid_date"), ("02/11/2026", "invalid_date"),
    ("2026-02-30T00:00:00Z", "invalid_date"), ("2026-11-02T25:00:00Z", "invalid_date"),
    ("2026-11-02T13:01:32+00:60", "invalid_date"), ("2026-11-02T13:01:32-00:00", "invalid_date"),
    ("20261102T130132Z", "invalid_date"), ("2026-11-02 13:01:32Z", "invalid_date"),
    ("2026-11-02T13:01:32.1234567Z", "invalid_date"),
    ("0001-01-01T00:00:00+01:00", "invalid_date"),
    ("9999-12-31T23:59:59-01:00", "invalid_date"),
])
def test_invalid_dates_are_rejected_without_substituting_now(value, code):
    assert_rejected(normalize([row(iso_date=value, date="ayer", iso_date_of_last_edit="2026-11-02T13:01:32Z")]), "iso_date", code)


@pytest.mark.parametrize("value", [1, 2, 3, 4, 5, 1.0, 2.0, 3.0, 4.0, 5.0])
def test_valid_ratings_become_strict_integers(value):
    rating = normalize([row(rating=value)]).with_text[0].rating
    assert rating == value and type(rating) is int


@pytest.mark.parametrize("value", [
    None, 0, 6, -1, 1.5, 4.9, "3", "3.0", True, False, [], {},
    float("nan"), float("inf"), -float("inf"), 10 ** 400,
])
def test_invalid_ratings_are_not_coerced_or_rounded(value):
    assert_rejected(normalize([row(rating=value)]), "rating", "invalid_rating")


@pytest.mark.parametrize("value", [None, "", "google", " Google ", "SerpApi", "Trip.com", "unknown", [], {}, True, "\ud800"])
def test_only_explicit_google_source_is_accepted(value):
    assert_rejected(normalize([row(source=value)]), "source", "unsupported_source")


def test_unknown_fields_and_metadata_are_ignored_without_mutation():
    data = row(images=[PRIVATE], response={"snippet": PRIVATE}, extra={"nested": [PRIVATE]})
    result = batch([data])
    before = deepcopy(result)
    normalized = normalize_serpapi_result(result, business_data_id=BUSINESS)
    assert result == before and data == before.pages[0].reviews[0].data
    assert normalized.with_text[0].business_data_id == BUSINESS
    assert not hasattr(normalized.with_text[0], "images")
    assert not hasattr(normalized, "place_info")


def test_mixed_batch_preserves_good_rows_and_positions():
    result = normalize(
        [row(review_id="one"), row(review_id="bad", rating=True)],
        [row(review_id="two", snippet=None, extracted_snippet=None), row(review_id=None)],
    )
    assert [item.external_review_id for item in result.with_text] == ["one"]
    assert [item.external_review_id for item in result.without_text] == ["two"]
    assert [(item.position.page, item.position.index, item.position.ordinal) for item in result.rejected] == [(1, 2, 2), (2, 2, 4)]
    assert [item.issues[0].code for item in result.rejected] == ["invalid_rating", "required"]
    assert result.counts.total == 4 and result.counts.rejected == 2
    assert_reconciled(result)


def test_identical_duplicates_across_pages_keep_one_with_occurrence_positions():
    result = normalize([row()], [row(), row()])
    assert len(result.with_text) == 1 and result.counts.duplicates == 2
    assert [item.position.ordinal for item in result.duplicates] == [2, 3]
    assert all(item.kept_position == result.with_text[0].position for item in result.duplicates)
    assert not result.conflicts and not result.rejected
    assert_reconciled(result)


def test_normalized_equivalence_ignores_extra_fields_and_native_numeric_date_forms():
    result = normalize([row()], [row(rating=4.0, iso_date="2026-11-02T06:01:32-07:00", extra=PRIVATE)])
    assert result.counts.duplicates == 1 and len(result.with_text) == 1
    assert_reconciled(result)


@pytest.mark.parametrize("changes", [
    {"rating": 5}, {"user": {"name": "Otro autor sintético"}},
    {"iso_date": "2026-11-03T13:01:32Z"},
    {"extracted_snippet": {"original": "Otro texto sintético"}},
    {"snippet": None, "extracted_snippet": None},
    {"snippet": "Texto original sintético", "extracted_snippet": None},
])
def test_conflicting_group_removes_all_versions_even_preceding_identical_repeats(changes):
    result = normalize([row(), row(review_id="unrelated"), row()], [row(**changes)])
    assert [item.external_review_id for item in result.with_text] == ["unrelated"]
    assert not result.without_text and not result.duplicates
    conflict, = result.conflicts
    assert len(conflict.records) == 3
    assert [item.position.ordinal for item in conflict.records] == [1, 3, 4]
    assert [item.position.ordinal for item in result.rejected] == [1, 3, 4]
    assert all(item.issues[0].code == "conflicting_duplicate" for item in result.rejected)
    assert result.counts.conflicting == result.counts.rejected == 3
    assert_reconciled(result)


def test_textless_duplicates_and_multiple_conflict_groups_reconcile():
    result = normalize([
        row(review_id="empty", snippet=None, extracted_snippet=None),
        row(review_id="empty", snippet=None, extracted_snippet=None),
        row(review_id="a"), row(review_id="a", rating=5),
        row(review_id="b"), row(review_id="b", rating=3),
        row(review_id="bad", rating=False),
    ])
    assert result.counts.without_text == result.counts.duplicates == 1
    assert result.counts.rejected == 5 and result.counts.conflicting == 4
    assert len(result.conflicts) == 2 and len(result.warnings) == 2
    assert_reconciled(result)


def test_same_external_id_in_distinct_businesses_is_not_a_global_identity():
    first = normalize([row()]).with_text[0]
    second = normalize([row()], business="0x123:0x789").with_text[0]
    assert first.external_review_id == second.external_review_id
    assert first.identity != second.identity


@pytest.mark.parametrize("reason,incomplete,limited", [
    ("no_next_token", False, False), ("empty_with_token", True, False),
    ("repeated_token", True, False), ("max_pages", True, True), ("error", True, False),
])
def test_fetch_state_is_preserved_for_partial_and_empty_results(reason, incomplete, limited):
    for pages in ([], [[row()], [row(review_id="two", rating=False)]]):
        result = normalize(*pages, stop_reason=reason, incomplete=incomplete, limited=limited)
        assert (result.stop_reason, result.incomplete, result.limited) == (reason, incomplete, limited)
        assert result.batch_error is None
        assert_reconciled(result)


@pytest.mark.parametrize("business", [None, "", " ", "arbitrary", "0x123", "0xZZ:0x123", "0x123:0x456 ", 7, True, [], {}, "\ud800"])
def test_invalid_context_is_batch_error_without_uncertain_records(business):
    result = normalize([row()], business=business, stop_reason="max_pages", incomplete=True, limited=True)
    assert result.batch_error.code == "invalid_business_context"
    assert result.batch_error.field == "business_data_id" and result.batch_error.position is None
    assert result.input_count == 0 and not result.with_text and not result.rejected
    assert result.incomplete and result.limited and result.stop_reason == "max_pages"
    assert_reconciled(result)


@pytest.mark.parametrize("data", [None, [], PRIVATE, True, 5])
def test_malformed_native_record_does_not_break_other_rows(data):
    result = normalize([data, row()])
    assert result.rejected[0].issues[0].code == "invalid_record"
    assert len(result.with_text) == 1 and result.input_count == 2
    assert_reconciled(result)


def test_unwrapped_native_item_is_rejected_without_exception():
    original = batch([row(), row(review_id="two")])
    page = replace(original.pages[0], reviews=(PRIVATE, original.pages[0].reviews[1]))
    result = normalize_serpapi_result(replace(original, pages=(page,)), business_data_id=BUSINESS)
    assert result.rejected[0].issues[0].code == "invalid_record"
    assert result.with_text[0].external_review_id == "two"
    assert_reconciled(result)


@pytest.mark.parametrize("changes", [
    {"pages": None}, {"pages": []}, {"pages": (PRIVATE,)},
    {"pages": (SerpApiPage(1, 200, "Success", None),)},
    {"pages": (SerpApiPage(True, 200, "Success", ()),)},
    {"pages": (SerpApiPage(PRIVATE, 200, "Success", ()),)},
    {"stop_reason": PRIVATE}, {"stop_reason": []}, {"incomplete": PRIVATE}, {"limited": None},
])
def test_malformed_envelope_is_safe_batch_error(changes):
    result = normalize_serpapi_result(replace(batch([row()]), **changes), business_data_id=BUSINESS)
    assert result.batch_error.code == "invalid_result" and result.input_count == 0
    assert result.incomplete and result.stop_reason is None
    assert PRIVATE not in repr(result)


@pytest.mark.parametrize("value", [None, [], {}, PRIVATE])
def test_non_result_input_returns_safe_batch_error(value):
    result = normalize_serpapi_result(value, business_data_id=BUSINESS)
    assert result.batch_error.code == "invalid_result" and result.input_count == 0


def test_counters_count_actual_entries_without_trusting_provider_record_count():
    native = replace(batch([row()]), record_count=999)
    result = normalize_serpapi_result(native, business_data_id=BUSINESS)
    assert result.counts.total == 1
    assert_reconciled(result)


def test_input_immutability_and_determinism_even_for_rejections_and_conflicts():
    native = batch([row(), row(rating=5), row(review_id="bad", user={"name": []})], [row(review_id="empty", snippet=None, extracted_snippet=None)])
    before = deepcopy(native)
    first = normalize_serpapi_result(native, business_data_id=BUSINESS)
    second = normalize_serpapi_result(native, business_data_id=BUSINESS)
    assert native == before and first == second
    with pytest.raises(FrozenInstanceError):
        first.without_text[0].content = "replacement"
    with pytest.raises(FrozenInstanceError):
        first.incomplete = True
    assert_reconciled(first)


def test_sensitive_values_do_not_appear_in_repr_issues_or_logs(caplog, capsys):
    data = row(review_id=PRIVATE, user={"name": PRIVATE}, extracted_snippet={"original": PRIVATE})
    accepted = normalize([data])
    conflict = normalize([data], [row(**{**data, "rating": 5})])
    rejected = normalize([row(review_id=PRIVATE, iso_date=PRIVATE)])
    warning = normalize([row(review_id=PRIVATE, user=None, snippet=None, extracted_snippet=None)])
    bad_context = normalize([data], business=PRIVATE)
    for result in (accepted, conflict, rejected, warning, bad_context):
        for obj in (result, result.counts, result.batch_error, *result.with_text, *result.without_text,
                    *result.conflicts, *result.rejected, *result.duplicates, *result.warnings):
            assert PRIVATE not in repr(obj) and PRIVATE not in str(obj)
    assert not caplog.records
    assert capsys.readouterr() == ("", "")


def test_pure_modules_import_only_contracts_and_standard_library():
    allowed = {
        "dataclasses", "datetime", "typing", "math", "re", "app.schemas.external_review", "app.schemas.serpapi",
    }
    for path in (BACKEND / "app/services/serpapi_normalizer.py", BACKEND / "app/schemas/external_review.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(item.name for item in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module)
        assert imported <= allowed


def test_isolated_import_and_execution_without_http_db_ai_or_file_writes():
    script = r'''
import importlib.abc, os, sys
sys.path.insert(0, sys.argv[1])
class NoExternalServices(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        forbidden = ('httpx', 'httpcore', 'sqlalchemy', 'sqlite3', 'fastapi', 'google',
                     'app.repositories', 'app.db', 'app.models', 'app.core',
                     'app.services.serpapi_client', 'app.services.ai_provider',
                     'app.services.summary_service', 'app.services.classification_service')
        if any(fullname == name or fullname.startswith(name + '.') for name in forbidden):
            raise AssertionError('Forbidden service import')
sys.meta_path.insert(0, NoExternalServices())
def audit(event, args):
    if event.startswith(('socket.', 'sqlite3.')):
        raise AssertionError('Forbidden IO')
    if event == 'open' and args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
        raise AssertionError('Forbidden file write')
sys.addaudithook(audit)
from app.schemas.serpapi import SerpApiPage, SerpApiResult, SerpApiReview
from app.services.serpapi_normalizer import normalize_serpapi_result
row = SerpApiReview({'review_id': 'synthetic', 'source': 'Google', 'iso_date': '2026-11-02T00:00:00Z', 'rating': 5})
native = SerpApiResult((SerpApiPage(1, 200, 'Success', (row,)),), None, None, 1, 1, 'no_next_token', False, False)
result = normalize_serpapi_result(native, business_data_id='0x123:0x456')
assert result.counts.without_text == 1 and result.batch_error is None
print('pure-normalization-ok')
'''
    env = {key: value for key, value in os.environ.items() if key not in ("SERPAPI_API_KEY", "SSLKEYLOGFILE")}
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script, str(BACKEND)],
        env=env, capture_output=True, text=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "pure-normalization-ok" and not completed.stderr
