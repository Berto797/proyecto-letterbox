import argparse
import sys

import psycopg

from extract import define_processed_name, extract, move_to_processed
from load import load_raw


def main(argv=None):
    """Ejecuta el pipeline completo de la watchlist.

    Extrae las películas del CSV de la carpeta input, las carga en la
    tabla raw_watchlist y, solo si la carga termina sin errores, mueve
    el CSV a la carpeta processed. Con la opción --keep-original lo
    copia en lugar de moverlo y conserva el original en input.

    Args:
        argv: Lista de argumentos de la línea de comandos, sin el
            nombre del programa. Si es None, se usan los de sys.argv.

    Raises:
        SystemExit: Con código 1 si falla algún paso del pipeline (CSV
            no encontrado o inválido, variables de entorno ausentes,
            error de PostgreSQL o fallo al mover o copiar el archivo).
            Con código 2 si los argumentos de la línea de comandos no
            son válidos (lo gestiona argparse).
    """
    parser = argparse.ArgumentParser(
        description="Carga la watchlist de Letterboxd en PostgreSQL"
    )
    parser.add_argument(
        "-k",
        "--keep-original",
        action="store_true",
        help="Copia el CSV a processed en lugar de moverlo "
        "(conserva el original en input)",
    )
    args = parser.parse_args(argv)

    try:
        csv_file, film_list = extract()
        csv_processed_path = define_processed_name(csv_file)
        load_raw(csv_processed_path, film_list)
        move_to_processed(
            csv_file, csv_processed_path, keep_original=args.keep_original
        )
        print(
            f"Se han cargado {len(film_list)} películas. "
            f"El CSV procesado se encuentra en {csv_processed_path}"
        )
    except (ValueError, OSError, KeyError, psycopg.Error) as e:
        print("El pipeline no se ha completado", file=sys.stderr)
        print(e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
