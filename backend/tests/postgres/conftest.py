"""Cada prueba usa un esquema nuevo; nunca reutiliza tablas del proyecto."""

import os
from uuid import uuid4

import pytest
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.connection import create_database_engine


@pytest.fixture()
def postgres_engine():
    url = os.environ.get("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Define TEST_POSTGRES_URL para ejecutar las pruebas de PostgreSQL")
    administration = create_database_engine(url)
    if administration.dialect.name != "postgresql":
        administration.dispose()
        pytest.fail("TEST_POSTGRES_URL debe apuntar a PostgreSQL")
    schema = "test_reviews_" + uuid4().hex
    database = None
    created = False
    try:
        with administration.begin() as connection:
            connection.execute(CreateSchema(schema))
        created = True
        database = create_database_engine(administration.url.update_query_dict({
            "options": f"-csearch_path={schema}",
        }))
        yield database
    finally:
        if database is not None:
            database.dispose()
        if created:
            with administration.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
        administration.dispose()
