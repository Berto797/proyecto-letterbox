import os

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb

load_dotenv()

MAPPING_HEADERS = {
    "Date": "watchlisted_at",
    "Name": "film_name",
    "Year": "film_year",
    "Letterboxd URI": "letterboxd_uri",
}


def _open_connection():
    return psycopg.connect(
        host="localhost",
        port=5432,
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def _build_row(csv_processed_path, film):
    row = {new: film[old] for old, new in MAPPING_HEADERS.items()}
    extras = {key: value for key, value in film.items() if key not in MAPPING_HEADERS}
    row["extra_fields"] = Jsonb(extras)
    row["source_file"] = csv_processed_path.name
    return row


def load_raw(csv_processed_path, film_list):
    """Inserta las películas extraídas del CSV en la tabla raw_watchlist.

    Las columnas obligatorias del CSV se guardan en sus columnas propias,
    según MAPPING_HEADERS. Cualquier columna adicional se guarda en
    extra_fields como JSONB. Todas las filas se insertan en una única
    transacción: si alguna falla, no se guarda ninguna.

    Args:


    Raises:

    """
    rows = [_build_row(csv_processed_path, film) for film in film_list]
    print(rows)

    with _open_connection() as conn:
        conn.execute("SELECT 1")


if __name__ == "__main__":
    from extract import define_processed_name, extract

    try:
        csv_file, film_list = extract()
        csv_processed_path = define_processed_name(csv_file)
        load_raw(csv_processed_path, film_list)
    except (ValueError, KeyError) as e:
        print(e)
