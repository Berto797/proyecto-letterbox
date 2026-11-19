from datetime import UTC, datetime

import psycopg
from psycopg.rows import TupleRow

from matching import MatchStatus

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


def insert_watchlist_row(
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


def insert_match(
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
