from pathlib import Path

import psycopg
import pytest

from load import _build_row, _open_connection, load_raw

FILM = {
    "Date": "2026-01-01",
    "Name": "Get Out",
    "Year": "2017",
    "Letterboxd URI": "https://boxd.it/eOCm",
}
SECOND_FILM = {
    "Date": "2026-01-02",
    "Name": "Portrait of a Lady on Fire",
    "Year": "2019",
    "Letterboxd URI": "https://boxd.it/jkPq",
}
CSV_PROCESSED_PATH = Path("processed/watchlist_20260101_00_00_00.csv")
EXPECTED_ROW = {
    "watchlisted_at": "2026-01-01",
    "film_name": "Get Out",
    "film_year": "2017",
    "letterboxd_uri": "https://boxd.it/eOCm",
    "source_file": "watchlist_20260101_00_00_00.csv",
}


@pytest.mark.parametrize(
    "film, expected_extras",
    [
        pytest.param(
            FILM,
            {},
            id="no_extras",
        ),
        pytest.param(
            {**FILM, "Score": "87"},
            {"Score": "87"},
            id="one_extra_column",
        ),
        pytest.param(
            {**FILM, "Score": "87", "Rating": "4.5"},
            {"Score": "87", "Rating": "4.5"},
            id="several_extra_columns",
        ),
        pytest.param(
            {**FILM, None: ["valor1", "valor2"]},
            {None: ["valor1", "valor2"]},
            id="extra_values_without_header",
        ),
    ],
)
def test_build_row(film, expected_extras):
    row = _build_row(CSV_PROCESSED_PATH, film)

    extra_fields = row.pop("extra_fields")
    assert extra_fields.obj == expected_extras
    assert row == EXPECTED_ROW


def test_load_raw_valid(clean_db):
    film_list = [FILM, SECOND_FILM]

    load_raw(CSV_PROCESSED_PATH, film_list)

    with _open_connection() as conn:
        rows = conn.execute(
            """
            SELECT watchlisted_at, film_name, film_year, letterboxd_uri
            FROM raw_watchlist
            ORDER BY id
            """
        ).fetchall()
    assert rows == [
        ("2026-01-01", "Get Out", "2017", "https://boxd.it/eOCm"),
        ("2026-01-02", "Portrait of a Lady on Fire", "2019", "https://boxd.it/jkPq"),
    ]


def test_load_raw_extra_fields(clean_db):
    film_list = [
        {
            **FILM,
            "Score": "87",
        },
        SECOND_FILM,
    ]

    load_raw(CSV_PROCESSED_PATH, film_list)

    with _open_connection() as conn:
        extra_fields = conn.execute(
            """
            SELECT extra_fields
            FROM raw_watchlist
            ORDER BY id
            """
        ).fetchall()
    assert extra_fields == [
        ({"Score": "87"},),
        ({},),
    ]


def test_load_raw_automatic_columns(clean_db):
    film_list = [FILM, SECOND_FILM]

    load_raw(CSV_PROCESSED_PATH, film_list)

    with _open_connection() as conn:
        automatic_columns = conn.execute(
            """
            SELECT id, source_file, loaded_at
            FROM raw_watchlist
            ORDER BY id
            """
        ).fetchall()
    ids = [row[0] for row in automatic_columns]
    source_files = [row[1] for row in automatic_columns]
    loaded_ats = [row[2] for row in automatic_columns]
    assert ids == [1, 2]
    assert source_files == ["watchlist_20260101_00_00_00.csv"] * 2
    assert None not in loaded_ats
    assert len(set(loaded_ats)) == 1


def test_load_raw_all_or_nothing(clean_db):
    film_list = [
        SECOND_FILM,
        {
            **FILM,
            "Name": "Get\x00Out",
        },
    ]

    with pytest.raises(psycopg.DataError):
        load_raw(CSV_PROCESSED_PATH, film_list)

    with _open_connection() as conn:
        count = conn.execute(
            """
            SELECT count(*) FROM raw_watchlist
            """
        ).fetchone()[0]
    assert count == 0


def test_load_raw_connection_error(monkeypatch):
    film_list = [FILM, SECOND_FILM]
    monkeypatch.setenv("POSTGRES_USER", "test_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "1234")
    monkeypatch.setenv("POSTGRES_DB", "test")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "1")

    with pytest.raises(psycopg.OperationalError):
        load_raw(CSV_PROCESSED_PATH, film_list)


def test_load_raw_missing_env_variable(monkeypatch):
    film_list = [FILM, SECOND_FILM]
    monkeypatch.setenv("POSTGRES_USER", "test_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "1234")
    monkeypatch.setenv("POSTGRES_DB", "test")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "1")
    monkeypatch.delenv("POSTGRES_PORT")

    with pytest.raises(KeyError, match="POSTGRES_PORT"):
        load_raw(CSV_PROCESSED_PATH, film_list)
