from dataclasses import dataclass

import psycopg
from psycopg.rows import TupleRow, class_row

from matching import MatchResult

GET_PENDING_FILMS = """
    SELECT DISTINCT ON (w.letterboxd_uri)
        w.letterboxd_uri, w.film_name, w.film_year
    FROM raw_watchlist AS w
    WHERE NOT EXISTS (
        SELECT 1 FROM tmdb_matches AS m
        WHERE m.letterboxd_uri = w.letterboxd_uri
    ) AND w.letterboxd_uri IS NOT NULL
    ORDER BY w.letterboxd_uri, w.loaded_at DESC, w.id DESC
"""
UPSERT_TMDB_MATCHES = """
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
    ON CONFLICT (letterboxd_uri) DO UPDATE
    SET tmdb_id = EXCLUDED.tmdb_id,
        match_status = EXCLUDED.match_status,
        matched_at = now()
"""


@dataclass(frozen=True)
class PendingFilm:
    """Película de la watchlist que aún no tiene emparejamiento en tmdb_matches"""

    letterboxd_uri: str
    film_name: str
    film_year: str


def get_pending_films(conn: psycopg.Connection[TupleRow]) -> list[PendingFilm]:
    """Obtiene las películas de la watchlist pendientes de emparejar con TMDB.

    Una película está pendiente si su letterboxd_uri no aparece en
    tmdb_matches, sea cual sea su match_status (también not_found, para
    no volver a buscarla). Como raw_watchlist guarda una copia de la
    watchlist por cada carga, devuelve una sola fila por letterboxd_uri,
    con los datos de la carga más reciente. Las filas sin letterboxd_uri
    se descartan.

    Args:
        conn: Conexión abierta a PostgreSQL, normalmente obtenida con
            open_connection.

    Returns:
        Lista de PendingFilm ordenada por letterboxd_uri. Vacía si no
        queda ninguna película pendiente.

    Raises:
        psycopg.Error: Si falla la consulta.
    """
    with conn.cursor(row_factory=class_row(PendingFilm)) as cur:
        result = cur.execute(GET_PENDING_FILMS).fetchall()
    return result


def save_match(
    conn: psycopg.Connection[TupleRow], letterboxd_uri: str, match_result: MatchResult
) -> None:
    """Guarda el resultado de emparejar una película en tmdb_matches.

    Se guardan todos los estados, también not_found (con tmdb_id nulo),
    para que la película no se vuelva a buscar. Si la letterboxd_uri ya
    existe en la tabla, sustituye su tmdb_id y match_status por los
    nuevos y actualiza matched_at. No hace commit: confirmar la
    transacción es responsabilidad de quien llama a la función.

    Args:
        conn: Conexión abierta a PostgreSQL, normalmente obtenida con
            open_connection.
        letterboxd_uri: URI de la película en Letterboxd, clave de
            tmdb_matches.
        match_result: Resultado del emparejamiento, normalmente devuelto
            por match_film.

    Raises:
        psycopg.Error: Si falla la inserción o la actualización.
    """
    parameters = {
        "letterboxd_uri": letterboxd_uri,
        "tmdb_id": match_result.tmdb_id,
        "match_status": match_result.status,
    }
    conn.execute(UPSERT_TMDB_MATCHES, parameters)
