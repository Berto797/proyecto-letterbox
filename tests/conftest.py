from collections.abc import Iterator, Mapping
from pathlib import Path

import psycopg
import pytest
from testcontainers.community.postgres import PostgresContainer

from db import open_connection

SQL_PATH = Path(__file__).parent.parent / "sql"


@pytest.fixture(scope="session")
def postgres_connection_info() -> Iterator[dict[str, str]]:
    with PostgresContainer("postgres:17") as postgres:
        host = postgres.get_container_host_ip()
        port = postgres.get_exposed_port(5432)
        dbname = postgres.dbname
        user = postgres.username
        password = postgres.password
        with psycopg.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
        ) as conn:
            for sql_file in sorted(SQL_PATH.glob("*.sql")):
                conn.execute(sql_file.read_text(encoding="utf-8"))
        yield {
            "POSTGRES_HOST": host,
            "POSTGRES_PORT": str(port),
            "POSTGRES_DB": dbname,
            "POSTGRES_USER": user,
            "POSTGRES_PASSWORD": password,
        }


@pytest.fixture()
def clean_db(
    postgres_connection_info: Mapping[str, str], monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    for key, value in postgres_connection_info.items():
        monkeypatch.setenv(key, value)

    with open_connection() as conn:
        conn.execute(
            "TRUNCATE raw_watchlist, tmdb_matches, raw_tmdb_movies RESTART IDENTITY"
        )

    yield
