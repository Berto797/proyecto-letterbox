import csv
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

REQUIRED_MANUAL_HEADERS = {"letterboxd_uri", "tmdb_id"}


@dataclass(frozen=True)
class ManualMatch:
    """Emparejamiento manual de una película de la watchlist con su id de TMDB"""

    letterboxd_uri: str
    tmdb_id: int


def _validate_manual_headers(path: Path, fieldnames: Sequence[str] | None) -> None:
    """Valida que el archivo no esté vacío y que tenga las columnas obligatorias"""
    if fieldnames is None:
        raise ValueError(f"Archivo {path.name} vacío")
    missing_headers = REQUIRED_MANUAL_HEADERS - set(fieldnames)
    if missing_headers:
        missing_names = ", ".join(sorted(missing_headers))
        raise ValueError(
            f"Faltan los encabezados: {missing_names} "
            f"en el CSV de emparejamiento manual {path.name} "
            "(comprueba que el separador sea una coma)"
        )


def _read_manual_rows(path: Path) -> list[tuple[int, dict[str | None, str | None]]]:
    """Lee las filas de manual_matches.csv junto con su número de línea"""
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            _validate_manual_headers(path, reader.fieldnames)
            return [(reader.line_num, row) for row in reader]
    except UnicodeDecodeError as e:
        raise ValueError(f"El archivo {path.name} no está codificado en UTF-8") from e


def _parse_manual_row(
    path: Path, row: Mapping[str | None, str | None], line_num: int
) -> ManualMatch:
    """Valida una fila de manual_matches.csv y la convierte en un ManualMatch"""
    letterboxd_uri = (row["letterboxd_uri"] or "").strip()
    tmdb_id_text = (row["tmdb_id"] or "").strip()
    if letterboxd_uri == "":
        raise ValueError(
            f"El letterboxd_uri de la línea {line_num} de {path.name} está vacío"
        )
    try:
        tmdb_id = int(tmdb_id_text)
    except ValueError as e:
        raise ValueError(
            f"El tmdb_id de la línea {line_num} de {path.name} "
            f"no es un número entero: {tmdb_id_text!r}"
        ) from e
    if tmdb_id <= 0:
        raise ValueError(
            f"El tmdb_id de la línea {line_num} de {path.name} "
            f"tiene que ser positivo: {tmdb_id}"
        )
    return ManualMatch(letterboxd_uri=letterboxd_uri, tmdb_id=tmdb_id)


def read_manual_matches(path: Path) -> list[ManualMatch]:
    """Lee los emparejamientos manuales del archivo manual_matches.csv.

    El archivo es opcional: si no existe, no hay emparejamientos
    manuales. Necesita las columnas letterboxd_uri y tmdb_id; las demás
    se ignoran, así que se pueden copiar filas de pending_matches.csv
    con el título y el año de cada película.

    Args:
        path: Ruta del archivo manual_matches.csv.

    Returns:
        Lista con un ManualMatch por fila, en el orden del archivo.
        Vacía si el archivo no existe o solo tiene los encabezados.

    Raises:
        ValueError: Si el archivo está vacío, no está codificado en
            UTF-8, le faltan columnas obligatorias o alguna fila tiene
            el letterboxd_uri vacío o repetido, o un tmdb_id que no es
            un entero positivo.
    """
    if not path.exists():
        return []
    rows = _read_manual_rows(path)
    manual_matches: list[ManualMatch] = []
    seen_uris: set[str] = set()
    for line_num, row in rows:
        manual_match = _parse_manual_row(path, row, line_num)
        if manual_match.letterboxd_uri in seen_uris:
            raise ValueError(
                f"El letterboxd_uri {manual_match.letterboxd_uri} de la línea "
                f"{line_num} de {path.name} está repetido"
            )
        seen_uris.add(manual_match.letterboxd_uri)
        manual_matches.append(manual_match)
    return manual_matches
