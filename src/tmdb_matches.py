from dataclasses import dataclass

import psycopg
from psycopg.rows import TupleRow, class_row

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
