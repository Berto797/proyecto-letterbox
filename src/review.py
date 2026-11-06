import csv
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg.rows import TupleRow

from db import open_connection
from matching import MatchResult, MatchStatus
from tmdb_matches import save_match

REQUIRED_MANUAL_HEADERS = {"letterboxd_uri", "tmdb_id"}
GET_KNOWN_URIS = """
    SELECT DISTINCT letterboxd_uri
    FROM raw_watchlist
    WHERE letterboxd_uri = ANY(%(uris)s)
"""


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


def _validate_known_uris(
    conn: psycopg.Connection[TupleRow],
    path: Path,
    manual_matches: Sequence[ManualMatch],
) -> None:
    """Valida que todos los letterboxd_uri del archivo manual estén en la watchlist"""
    uris = [manual_match.letterboxd_uri for manual_match in manual_matches]
    manual_uris = set(uris)
    rows = conn.execute(GET_KNOWN_URIS, {"uris": uris}).fetchall()
    known_uris = {row[0] for row in rows}
    unknown_uris = manual_uris - known_uris
    if unknown_uris:
        unknown_names = ", ".join(sorted(unknown_uris))
        raise ValueError(
            f"Los letterboxd_uri {unknown_names} de {path.name} "
            "no están en la watchlist"
        )


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


def apply_manual_matches(path: Path) -> int:
    """Guarda en tmdb_matches los emparejamientos de manual_matches.csv.

    Lee el archivo con read_manual_matches y guarda cada fila con
    save_match y el estado manual, sin buscar en TMDB: el tmdb_id se
    guarda tal cual, sin comprobar que exista. Si la película ya tenía
    un emparejamiento, lo sustituye. Antes de guardar, comprueba que
    todos los letterboxd_uri estén en la watchlist. Abre su propia
    conexión y guarda todas las filas en una sola transacción: si algo
    falla, no se guarda ninguna. Si el archivo no existe o no tiene
    filas, no se conecta a PostgreSQL.

    Args:
        path: Ruta del archivo manual_matches.csv.

    Returns:
        Número de emparejamientos manuales guardados. 0 si el archivo no
        existe o solo tiene los encabezados.

    Raises:
        ValueError: Si el archivo no es válido (ver read_manual_matches)
            o algún letterboxd_uri no está en la watchlist.
        KeyError: Si falta alguna de las variables POSTGRES_*.
        psycopg.Error: Si falla la conexión con PostgreSQL, la consulta
            o el guardado de un emparejamiento.
    """
    manual_matches = read_manual_matches(path)
    if not manual_matches:
        return 0
    with open_connection() as conn:
        _validate_known_uris(conn, path, manual_matches)
        for manual_match in manual_matches:
            save_match(
                conn,
                manual_match.letterboxd_uri,
                MatchResult(tmdb_id=manual_match.tmdb_id, status=MatchStatus.MANUAL),
            )
    return len(manual_matches)
