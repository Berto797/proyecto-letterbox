from datetime import UTC, datetime

import psycopg
import pytest
from psycopg.rows import TupleRow

from db import open_connection
from matching import MatchStatus
from tmdb_matches import PendingFilm, get_pending_films

INSERT_WATCHLIST_ROW = """
    INSERT INTO raw_watchlist (
        letterboxd_uri,
        film_name,
        film_year,
        loaded_at,
        source_file
    )
    VALUES (
        %(letterboxd_uri)s,
        %(film_name)s,
        %(film_year)s,
        %(loaded_at)s,
        %(source_file)s
    )
"""
INSERT_MATCH = """
    INSERT INTO tmdb_matches (
        letterboxd_uri,
        tmdb_id,
        match_status
    )
    VALUES (
        %(letterboxd_uri)s,
        %(tmdb_id)s,
        %(match_status)s
    )
"""
OLDER_LOAD = datetime(2026, 1, 1, tzinfo=UTC)
NEWER_LOAD = datetime(2026, 2, 1, tzinfo=UTC)


def _insert_watchlist_row(
    conn: psycopg.Connection[TupleRow],
    letterboxd_uri: str | None,
    film_name: str,
    film_year: str,
    loaded_at: datetime,
) -> None:
    """Inserta una fila en raw_watchlist con la fecha de carga indicada"""
    row = {
        "letterboxd_uri": letterboxd_uri,
        "film_name": film_name,
        "film_year": film_year,
        "loaded_at": loaded_at,
        "source_file": "watchlist_1.csv",
    }
    with conn.cursor() as cur:
        cur.execute(INSERT_WATCHLIST_ROW, row)


def _insert_match(
    conn: psycopg.Connection[TupleRow],
    letterboxd_uri: str,
    tmdb_id: int | None,
    status: MatchStatus,
) -> None:
    """Inserta un emparejamiento en tmdb_matches"""
    row = {
        "letterboxd_uri": letterboxd_uri,
        "tmdb_id": tmdb_id,
        "match_status": status,
    }
    with conn.cursor() as cur:
        cur.execute(INSERT_MATCH, row)


def test_get_pending_films_empty(clean_db: None) -> None:
    with open_connection() as conn:
        result = get_pending_films(conn)

    assert result == []


def test_get_pending_films_returns_all(clean_db: None) -> None:
    with open_connection() as conn:
        _insert_watchlist_row(
            conn,
            "https://boxd.it/aaa",
            "Get Out",
            "2017",
            NEWER_LOAD,
        )
        _insert_watchlist_row(
            conn,
            "https://boxd.it/bbb",
            "Todavía",
            "",
            NEWER_LOAD,
        )

        result = get_pending_films(conn)

    assert result == [
        PendingFilm("https://boxd.it/aaa", "Get Out", "2017"),
        PendingFilm("https://boxd.it/bbb", "Todavía", ""),
    ]


def test_get_pending_films_latest_load(clean_db: None) -> None:
    with open_connection() as conn:
        # La más reciente se inserta primero para que tenga el id menor:
        # así se comprueba que gana loaded_at y no id
        _insert_watchlist_row(
            conn,
            "https://boxd.it/aaa",
            "2046",
            "2004",
            NEWER_LOAD,
        )
        _insert_watchlist_row(
            conn,
            "https://boxd.it/aaa",
            "Get Out",
            "2017",
            OLDER_LOAD,
        )

        result = get_pending_films(conn)

    assert result == [PendingFilm("https://boxd.it/aaa", "2046", "2004")]


def test_get_pending_films_same_load_highest_id(clean_db: None) -> None:
    with open_connection() as conn:
        _insert_watchlist_row(
            conn,
            "https://boxd.it/aaa",
            "2046",
            "2004",
            NEWER_LOAD,
        )
        _insert_watchlist_row(
            conn,
            "https://boxd.it/aaa",
            "Get Out",
            "2017",
            NEWER_LOAD,
        )

        result = get_pending_films(conn)

    assert result == [PendingFilm("https://boxd.it/aaa", "Get Out", "2017")]


@pytest.mark.parametrize(
    "tmdb_id, match_status",
    [
        pytest.param(1234, MatchStatus.MATCHED, id="matched"),
        pytest.param(None, MatchStatus.NOT_FOUND, id="not_found"),
    ],
)
def test_get_pending_films_excludes_saved_matches(
    tmdb_id: int | None, match_status: MatchStatus, clean_db: None
) -> None:
    with open_connection() as conn:
        _insert_watchlist_row(
            conn,
            "https://boxd.it/aaa",
            "Get Out",
            "2017",
            NEWER_LOAD,
        )
        _insert_watchlist_row(
            conn,
            "https://boxd.it/bbb",
            "Todavía",
            "",
            NEWER_LOAD,
        )
        _insert_match(conn, "https://boxd.it/aaa", tmdb_id, match_status)

        result = get_pending_films(conn)

    assert result == [PendingFilm("https://boxd.it/bbb", "Todavía", "")]


def test_get_pending_films_excludes_null_uri(clean_db: None) -> None:
    with open_connection() as conn:
        _insert_watchlist_row(
            conn,
            None,
            "Get Out",
            "2017",
            NEWER_LOAD,
        )
        _insert_watchlist_row(
            conn,
            "https://boxd.it/bbb",
            "Todavía",
            "",
            NEWER_LOAD,
        )

        result = get_pending_films(conn)

    assert result == [PendingFilm("https://boxd.it/bbb", "Todavía", "")]
