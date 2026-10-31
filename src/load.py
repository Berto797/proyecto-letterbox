from collections.abc import Mapping, Sequence
from pathlib import Path

from psycopg.types.json import Jsonb

from db import open_connection

MAPPING_HEADERS = {
    "Date": "watchlisted_at",
    "Name": "film_name",
    "Year": "film_year",
    "Letterboxd URI": "letterboxd_uri",
}

INSERT_RAW_WATCHLIST = """
    INSERT INTO raw_watchlist (
        watchlisted_at,
        film_name,
        film_year,
        letterboxd_uri,
        extra_fields,
        source_file
    )
    VALUES (
        %(watchlisted_at)s,
        %(film_name)s,
        %(film_year)s,
        %(letterboxd_uri)s,
        %(extra_fields)s,
        %(source_file)s
    )
"""


def _build_row(
    csv_processed_path: Path, film: Mapping[str, str]
) -> dict[str, str | Jsonb]:
    """Construye la fila de raw_watchlist de una película.

    Además de las columnas obligatorias, añade extra_fields con las
    columnas desconocidas y source_file con el nombre del CSV procesado.
    """
    row: dict[str, str | Jsonb] = {
        new: film[old] for old, new in MAPPING_HEADERS.items()
    }
    extras = {key: value for key, value in film.items() if key not in MAPPING_HEADERS}
    row["extra_fields"] = Jsonb(extras)
    row["source_file"] = csv_processed_path.name
    return row


def load_raw(csv_processed_path: Path, film_list: Sequence[Mapping[str, str]]) -> None:
    """Inserta las películas extraídas del CSV en la tabla raw_watchlist.

    Las columnas obligatorias del CSV se guardan en sus columnas propias,
    según MAPPING_HEADERS. Cualquier columna adicional se guarda en
    extra_fields como JSONB. Todas las filas se insertan en una única
    transacción: si alguna falla, no se guarda ninguna.

    Args:
        csv_processed_path: Ruta del CSV en la carpeta processed,
            normalmente obtenida con define_processed_name. Su nombre
            se guarda en la columna source_file.
        film_list: Lista de diccionarios devuelta por extract(), uno
            por película, con los encabezados del CSV como claves.

    Raises:
        KeyError: Si falta alguna variable de conexión en el entorno
            (POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER
            o POSTGRES_PASSWORD).
        psycopg.Error: Si falla la conexión con PostgreSQL o la
            inserción de las filas.
    """
    rows = [_build_row(csv_processed_path, film) for film in film_list]

    with open_connection() as conn, conn.cursor() as cur:
        cur.executemany(INSERT_RAW_WATCHLIST, rows)
