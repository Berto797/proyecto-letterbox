from collections import Counter
from datetime import UTC, datetime
from typing import Any

import psycopg
import pytest
import requests
from psycopg.rows import TupleRow

from db import open_connection
from matching import MatchResult, MatchStatus
from tmdb_matches import PendingFilm, get_pending_films, match_pending_films, save_match

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
        match_status,
        matched_at
    )
    VALUES (
        %(letterboxd_uri)s,
        %(tmdb_id)s,
        %(match_status)s,
        %(matched_at)s
    )
"""
SELECT_MATCHES = """
    SELECT letterboxd_uri, tmdb_id, match_status
    FROM tmdb_matches
    ORDER BY letterboxd_uri
"""
OLDER_LOAD = datetime(2026, 1, 1, tzinfo=UTC)
NEWER_LOAD = datetime(2026, 2, 1, tzinfo=UTC)
GET_OUT_RESULT = {
    "id": 1234,
    "title": "Get Out",
    "original_title": "Get Out",
    "vote_count": 300,
}


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
    match_status: MatchStatus,
    matched_at: datetime = OLDER_LOAD,
) -> None:
    """Inserta un emparejamiento en tmdb_matches"""
    row = {
        "letterboxd_uri": letterboxd_uri,
        "tmdb_id": tmdb_id,
        "match_status": match_status,
        "matched_at": matched_at,
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
        PendingFilm(
            letterboxd_uri="https://boxd.it/aaa", film_name="Get Out", film_year="2017"
        ),
        PendingFilm(
            letterboxd_uri="https://boxd.it/bbb", film_name="Todavía", film_year=""
        ),
    ]


def test_get_pending_films_latest_load(clean_db: None) -> None:
    with open_connection() as conn:
        # La más reciente se inserta primero para que tenga el id menor:
        # así se comprueba que gana loaded_at y no id
        _insert_watchlist_row(
            conn,
            "https://boxd.it/aaa",
            "Omaha",
            "2025",
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

    assert result == [
        PendingFilm(
            letterboxd_uri="https://boxd.it/aaa", film_name="Omaha", film_year="2025"
        )
    ]


def test_get_pending_films_same_load_highest_id(clean_db: None) -> None:
    with open_connection() as conn:
        _insert_watchlist_row(
            conn,
            "https://boxd.it/aaa",
            "Omaha",
            "2025",
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

    assert result == [
        PendingFilm(
            letterboxd_uri="https://boxd.it/aaa", film_name="Get Out", film_year="2017"
        )
    ]


@pytest.mark.parametrize(
    "tmdb_id, match_status",
    [
        pytest.param(1234, MatchStatus.MATCHED, id="matched"),
        pytest.param(None, MatchStatus.NOT_FOUND, id="not_found"),
    ],
)
def test_get_pending_films_excludes_saved_matches(
    clean_db: None, tmdb_id: int | None, match_status: MatchStatus
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

    assert result == [
        PendingFilm(
            letterboxd_uri="https://boxd.it/bbb", film_name="Todavía", film_year=""
        )
    ]


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

    assert result == [
        PendingFilm(
            letterboxd_uri="https://boxd.it/bbb", film_name="Todavía", film_year=""
        )
    ]


@pytest.mark.parametrize(
    "tmdb_id, match_status",
    [
        pytest.param(1234, MatchStatus.MATCHED, id="matched"),
        pytest.param(None, MatchStatus.NOT_FOUND, id="not_found"),
    ],
)
def test_save_match_inserts(
    clean_db: None, tmdb_id: int | None, match_status: MatchStatus
) -> None:
    match_result = MatchResult(tmdb_id=tmdb_id, status=match_status)

    with open_connection() as conn:
        save_match(conn, "https://boxd.it/aaa", match_result)

        rows = conn.execute(SELECT_MATCHES).fetchall()

    assert rows == [("https://boxd.it/aaa", tmdb_id, match_status)]


def test_save_match_replaces_existing_match(clean_db: None) -> None:
    match_result = MatchResult(tmdb_id=4321, status=MatchStatus.MANUAL)

    with open_connection() as conn:
        _insert_match(conn, "https://boxd.it/aaa", 1234, MatchStatus.AMBIGUOUS)

        save_match(conn, "https://boxd.it/aaa", match_result)

        rows = conn.execute(
            """
            SELECT letterboxd_uri, tmdb_id, match_status, matched_at
            FROM tmdb_matches
            """
        ).fetchall()

    assert len(rows) == 1
    letterboxd_uri, tmdb_id, match_status, matched_at = rows[0]
    assert (letterboxd_uri, tmdb_id, match_status) == (
        "https://boxd.it/aaa",
        4321,
        MatchStatus.MANUAL,
    )
    assert matched_at > OLDER_LOAD


def test_save_match_removes_film_from_pending(clean_db: None) -> None:
    match_result = MatchResult(tmdb_id=1234, status=MatchStatus.MATCHED)

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

        pending_before = get_pending_films(conn)
        save_match(conn, "https://boxd.it/aaa", match_result)
        pending_after = get_pending_films(conn)

    assert pending_before == [
        PendingFilm(
            letterboxd_uri="https://boxd.it/aaa", film_name="Get Out", film_year="2017"
        ),
        PendingFilm(
            letterboxd_uri="https://boxd.it/bbb", film_name="Todavía", film_year=""
        ),
    ]
    assert pending_after == [
        PendingFilm(
            letterboxd_uri="https://boxd.it/bbb", film_name="Todavía", film_year=""
        )
    ]


def test_match_pending_films_empty(clean_db: None) -> None:
    calls: list[tuple[str, str | None]] = []

    def fake_search(title: str, search_year: str | None) -> list[dict[str, Any]]:
        calls.append((title, search_year))
        return []

    result = match_pending_films(fake_search)

    assert result == Counter()
    assert calls == []


def test_match_pending_films_saves_and_counts(clean_db: None) -> None:
    calls: list[tuple[str, str | None]] = []
    responses = {
        "Get Out": [GET_OUT_RESULT],
        "Todavía": [],
    }

    def fake_search(title: str, search_year: str | None) -> list[dict[str, Any]]:
        calls.append((title, search_year))
        return responses[title]

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

    result = match_pending_films(fake_search)

    with open_connection() as conn:
        rows = conn.execute(SELECT_MATCHES).fetchall()

    assert rows == [
        ("https://boxd.it/aaa", 1234, MatchStatus.MATCHED),
        ("https://boxd.it/bbb", None, MatchStatus.NOT_FOUND),
    ]
    assert result == Counter({MatchStatus.MATCHED: 1, MatchStatus.NOT_FOUND: 1})
    assert calls == [("Get Out", "2017"), ("Todavía", None)]


def test_match_pending_films_skips_saved_matches(clean_db: None) -> None:
    calls: list[tuple[str, str | None]] = []
    responses = {
        "Get Out": [{**GET_OUT_RESULT, "id": 4321}],
        "Todavía": [],
    }

    def fake_search(title: str, search_year: str | None) -> list[dict[str, Any]]:
        calls.append((title, search_year))
        return responses[title]

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
        _insert_match(conn, "https://boxd.it/aaa", 1234, MatchStatus.MANUAL)

    result = match_pending_films(fake_search)

    with open_connection() as conn:
        rows = conn.execute(SELECT_MATCHES).fetchall()

    assert rows == [
        ("https://boxd.it/aaa", 1234, MatchStatus.MANUAL),
        ("https://boxd.it/bbb", None, MatchStatus.NOT_FOUND),
    ]
    assert result == Counter({MatchStatus.NOT_FOUND: 1})
    assert calls == [("Todavía", None)]


def test_match_pending_films_keeps_previous_on_error(clean_db: None) -> None:
    calls: list[tuple[str, str | None]] = []
    responses = {"Get Out": [GET_OUT_RESULT]}

    def fake_search(title: str, search_year: str | None) -> list[dict[str, Any]]:
        calls.append((title, search_year))
        if title == "Todavía":
            raise requests.HTTPError("500")
        return responses[title]

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

    with pytest.raises(requests.HTTPError):
        match_pending_films(fake_search)

    with open_connection() as conn:
        rows = conn.execute(SELECT_MATCHES).fetchall()

    assert rows == [("https://boxd.it/aaa", 1234, MatchStatus.MATCHED)]
    assert calls == [("Get Out", "2017"), ("Todavía", None)]
