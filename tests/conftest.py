from pathlib import Path

import psycopg
import pytest
from testcontainers.community.postgres import PostgresContainer

from load import _open_connection

SQL_FILE = Path(__file__).parent.parent / "sql" / "01_create_raw_watchlist.sql"


@pytest.fixture(scope="session")
def postgres_connection_info():
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
            conn.execute(SQL_FILE.read_text(encoding="utf-8"))
        yield {
            "POSTGRES_HOST": host,
            "POSTGRES_PORT": str(port),
            "POSTGRES_DB": dbname,
            "POSTGRES_USER": user,
            "POSTGRES_PASSWORD": password,
        }


@pytest.fixture()
def clean_db(postgres_connection_info, monkeypatch):
    for key, value in postgres_connection_info.items():
        monkeypatch.setenv(key, value)

    with _open_connection() as conn:
        conn.execute("TRUNCATE raw_watchlist RESTART IDENTITY")

    yield
