import argparse
import os
import sys
from collections.abc import Sequence

import psycopg
import requests
from dotenv import load_dotenv

from extract import define_processed_name, extract, move_to_processed
from load import load_raw
from tmdb_client import TMDBClient
from tmdb_matches import match_pending_films


def _load_watchlist(keep_original: bool) -> None:
    """Extrae la watchlist, la carga en raw_watchlist y mueve el CSV a processed"""
    csv_file, film_list = extract()
    csv_processed_path = define_processed_name(csv_file)
    load_raw(csv_processed_path, film_list)
    move_to_processed(csv_file, csv_processed_path, keep_original=keep_original)
    print(
        f"Se han cargado {len(film_list)} películas. "
        f"El CSV procesado se encuentra en {csv_processed_path}"
    )


def _match_films() -> None:
    """Empareja con TMDB las películas pendientes e imprime un resumen por estado"""
    token = os.environ.get("TMDB_TOKEN")
    if not token:
        raise ValueError("Falta TMDB_TOKEN en el archivo .env")
    client = TMDBClient(token)
    counts = match_pending_films(client.search_movies)
    if not counts:
        print("No hay películas pendientes de emparejar")
    else:
        status_counts = ", ".join(
            [f"{status} {count}" for status, count in counts.items()]
        )
        print(f"Se han emparejado {counts.total()} películas: {status_counts}")


def main(argv: Sequence[str] | None = None) -> None:
    """Ejecuta el pipeline completo de la watchlist.

    Extrae las películas del CSV de la carpeta input, las carga en la
    tabla raw_watchlist y, solo si la carga termina sin errores, mueve
    el CSV a la carpeta processed. Con la opción --keep-original lo
    copia en lugar de moverlo y conserva el original en input. Después
    empareja con TMDB las películas pendientes, guarda los resultados en
    tmdb_matches e imprime un resumen por estado. Con la opción
    --match-only solo hace el emparejamiento, sin cargar ningún CSV.

    Args:
        argv: Argumentos de la línea de comandos, sin el nombre del
            programa. Si es None, se usan los de sys.argv.

    Raises:
        SystemExit: Con código 1 si falla algún paso del pipeline (CSV
            no encontrado o inválido, variables de entorno ausentes o
            TMDB_TOKEN vacío, error de PostgreSQL, fallo al mover o
            copiar el archivo o error en la petición a TMDB). Con código
            2 si los argumentos de la línea de comandos no son válidos
            (lo gestiona argparse).
    """
    parser = argparse.ArgumentParser(
        description="Carga la watchlist de Letterboxd en PostgreSQL "
        "y la empareja con TMDB"
    )
    parser.add_argument(
        "-k",
        "--keep-original",
        action="store_true",
        help="Copia el CSV a processed en lugar de moverlo "
        "(conserva el original en input)",
    )
    parser.add_argument(
        "-m",
        "--match-only",
        action="store_true",
        help="Solo empareja con TMDB las películas pendientes, sin cargar ningún CSV",
    )
    args = parser.parse_args(argv)

    try:
        if not args.match_only:
            _load_watchlist(keep_original=args.keep_original)
        _match_films()
    except (
        ValueError,
        OSError,
        KeyError,
        psycopg.Error,
        requests.RequestException,
    ) as e:
        print("El pipeline no se ha completado", file=sys.stderr)
        print(e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    load_dotenv()
    main()
