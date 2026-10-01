import csv
import shutil
from datetime import UTC, datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = PROJECT_DIR / "data" / "input"
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"

REQUIRED_HEADERS = {"Date", "Name", "Year", "Letterboxd URI"}
TIMESTAMP_FORMAT = "%Y%m%d_%H_%M_%S"


def _get_csv_files(input_path):
    """Se obtiene lista de .csv en input_path"""
    csv_files = list(input_path.glob("*.csv"))
    return csv_files


def _get_single_csv(input_path, csv_files):
    """Comprueba que el número de CSV sea 1 y, si es así, te devuelve la ruta del archivo CSV"""
    if len(csv_files) == 0:
        raise FileNotFoundError(f"No se encontró ningún CSV en la ruta: {input_path}")
    if len(csv_files) > 1:
        csv_files_names = [path.name for path in csv_files]
        raise ValueError(
            f"Se esperaba 1 archivo CSV y en la ruta hay {len(csv_files)}. Los CSV encontrados son los siguientes: {', '.join(sorted(csv_files_names))}"
        )
    return csv_files[0]


def _extract_csv(csv_file):
    """Extrae la información del .csv"""
    try:
        with open(csv_file, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            _validate_headers(csv_file, reader.fieldnames)
            film_list = list(reader)
            _validate_has_films(csv_file, film_list)
            return film_list
    except UnicodeDecodeError as e:
        raise ValueError(
            f"El archivo {csv_file.name} no está codificado en UTF-8"
        ) from e


def _validate_headers(csv_file, fieldnames):
    """Valida que el archivo no esté vacío y que los headers son los esperados"""
    if fieldnames is None:
        raise ValueError(f"Archivo {csv_file.name} vacío")
    missing_headers = REQUIRED_HEADERS - set(fieldnames)
    if missing_headers:
        raise ValueError(
            f"Faltan los encabezados: {', '.join(sorted(missing_headers))} en el CSV {csv_file.name}"
        )


def _validate_has_films(csv_file, film_list):
    """Comprueba que el CSV tiene películas"""
    if len(film_list) == 0:
        raise ValueError(
            f"No se han encontrado películas en el archivo CSV {csv_file.name}"
        )


def move_to_processed(csv_file, keep_original=False):
    """Mueve o copia el CSV procesado a la carpeta processed.

    Al nombre del archivo se le añade un sufijo con la fecha y hora
    actuales, según el formato definido en TIMESTAMP_FORMAT.

    Args:
        csv_file: Ruta del CSV a mover o copiar.
        keep_original: Si es True, copia el archivo y conserva el original
            en input. Si es False, lo mueve.

    Returns:
        Ruta del archivo en la carpeta processed.

    Raises:
        OSError: Si no se puede copiar o mover el archivo (por ejemplo,
            si no existe la carpeta de destino o no hay permisos).
    """
    current_time = datetime.now(UTC).strftime(TIMESTAMP_FORMAT)
    csv_name = csv_file.stem
    csv_extension = csv_file.suffix
    csv_processed_name = f"{csv_name}_{current_time}{csv_extension}"
    csv_processed_path = PROCESSED_DIR / csv_processed_name
    if keep_original:
        shutil.copy2(csv_file, csv_processed_path)
    else:
        shutil.move(csv_file, csv_processed_path)
    return csv_processed_path


def extract():
    """Localiza el CSV de la watchlist en INPUT_DIR, lo valida y lee sus filas.

    Returns:
        Una tupla (csv_file, film_list), donde csv_file es la ruta del CSV
        leído y film_list es una lista de diccionarios, uno por película,
        con los encabezados del CSV como claves.

    Raises:
        FileNotFoundError: Si no hay ningún CSV en INPUT_DIR.
        ValueError: Si hay más de un CSV, si el archivo está vacío, si
            faltan encabezados obligatorios, si no contiene películas o
            si no está codificado en UTF-8.
    """
    csv_files = _get_csv_files(INPUT_DIR)
    csv_file = _get_single_csv(INPUT_DIR, csv_files)
    film_list = _extract_csv(csv_file)
    return csv_file, film_list


if __name__ == "__main__":
    try:
        csv_file, film_list = extract()
        csv_processed_path = move_to_processed(csv_file, keep_original=True)
        print(csv_processed_path)
    except (FileNotFoundError, ValueError) as e:
        print(e)
