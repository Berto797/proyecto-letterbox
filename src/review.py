import csv
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

import psycopg
from psycopg.rows import TupleRow, class_row

from db import open_connection
from matching import MatchResult, MatchStatus
from tmdb_matches import save_match

REQUIRED_MANUAL_HEADERS = {"letterboxd_uri", "tmdb_id"}
GET_KNOWN_URIS = """
    SELECT DISTINCT letterboxd_uri
    FROM raw_watchlist
    WHERE letterboxd_uri = ANY(%(uris)s)
"""
REVIEW_STATUSES = [MatchStatus.AMBIGUOUS, MatchStatus.NOT_FOUND]
GET_FILMS_TO_REVIEW = """
    WITH latest_watchlist AS (
        SELECT DISTINCT ON (letterboxd_uri)
            letterboxd_uri, film_name, film_year
        FROM raw_watchlist
        ORDER BY letterboxd_uri, loaded_at DESC, id DESC
    )
    SELECT w.letterboxd_uri, w.film_name, w.film_year, m.match_status, m.tmdb_id
    FROM latest_watchlist AS w
    INNER JOIN tmdb_matches AS m
        ON m.letterboxd_uri = w.letterboxd_uri
    WHERE m.match_status = ANY(%(statuses)s)
    ORDER BY m.match_status, w.film_name, w.letterboxd_uri
"""
REVIEW_HEADERS = [
    "letterboxd_uri",
    "tmdb_id",
    "film_name",
    "film_year",
    "match_status",
    "tmdb_url",
]
TMDB_MOVIE_URL = "https://www.themoviedb.org/movie/"
TMDB_SEARCH_URL = "https://www.themoviedb.org/search/movie?query="


@dataclass(frozen=True)
class ManualMatch:
    """Emparejamiento manual de una película de la watchlist con su id de TMDB"""

    letterboxd_uri: str
    tmdb_id: int


@dataclass(frozen=True)
class FilmToReview:
    """Película de la watchlist con emparejamiento ambiguous o not_found por revisar.

    El tmdb_id es el candidato propuesto por el emparejamiento automático
    en las ambiguous, y None en las not_found.
    """

    letterboxd_uri: str
    film_name: str
    film_year: str
    match_status: str
    tmdb_id: int | None


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


def _tmdb_url(film: FilmToReview) -> str:
    """Devuelve el enlace a la ficha en TMDB o, si no hay tmdb_id, a su búsqueda"""
    if film.tmdb_id is None:
        return TMDB_SEARCH_URL + quote_plus(film.film_name)
    return TMDB_MOVIE_URL + str(film.tmdb_id)


def _write_review_csv(path: Path, films: Sequence[FilmToReview]) -> None:
    """Escribe las películas por revisar en un CSV, creando la carpeta si no existe"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REVIEW_HEADERS)
        writer.writeheader()
        for film in films:
            writer.writerow(
                {
                    "letterboxd_uri": film.letterboxd_uri,
                    "tmdb_id": film.tmdb_id,
                    "film_name": film.film_name,
                    "film_year": film.film_year,
                    "match_status": film.match_status,
                    "tmdb_url": _tmdb_url(film),
                }
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


def get_films_to_review(conn: psycopg.Connection[TupleRow]) -> list[FilmToReview]:
    """Obtiene las películas de la watchlist que hay que revisar a mano.

    Son las que tienen en tmdb_matches el match_status ambiguous o
    not_found. Como raw_watchlist guarda una copia de la watchlist por
    cada carga, devuelve una sola fila por letterboxd_uri, con el título
    y el año de la carga más reciente.

    Args:
        conn: Conexión abierta a PostgreSQL, normalmente obtenida con
            open_connection.

    Returns:
        Lista de FilmToReview ordenada por match_status (primero las
        ambiguous), después por título y por último por letterboxd_uri.
        Vacía si no hay ninguna película que revisar.

    Raises:
        psycopg.Error: Si falla la consulta.
    """
    with conn.cursor(row_factory=class_row(FilmToReview)) as cur:
        result = cur.execute(
            GET_FILMS_TO_REVIEW, {"statuses": REVIEW_STATUSES}
        ).fetchall()
    return result


def write_review_file(path: Path) -> int:
    """Escribe en un CSV las películas que hay que revisar a mano.

    Obtiene las películas ambiguous y not_found con get_films_to_review y
    las escribe en el archivo, con un enlace a TMDB para comprobar cada
    una. Las cuatro primeras columnas siguen el orden de
    manual_matches.csv, así que se pueden copiar filas enteras de un
    archivo al otro. El archivo se regenera en cada ejecución, aunque no
    haya ninguna película que revisar (en ese caso solo tiene los
    encabezados), para que nunca quede uno antiguo con películas ya
    resueltas. Si la carpeta no existe, la crea. Abre su propia conexión
    y la cierra antes de escribir el archivo.

    Args:
        path: Ruta del archivo de revisión, normalmente
            data/review/pending_matches.csv.

    Returns:
        Número de películas escritas en el archivo. 0 si no hay ninguna
        que revisar.

    Raises:
        KeyError: Si falta alguna de las variables POSTGRES_*.
        psycopg.Error: Si falla la conexión con PostgreSQL o la consulta.
        OSError: Si no se puede crear la carpeta o escribir el archivo.
    """
    with open_connection() as conn:
        films = get_films_to_review(conn)
    _write_review_csv(path, films)
    return len(films)
