import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

type SearchFunction = Callable[[str, str | None], list[dict[str, Any]]]


class MatchStatus(StrEnum):
    """Estados posibles de un emparejamiento en tmdb_matches"""

    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"
    MANUAL = "manual"


@dataclass(frozen=True)
class MatchResult:
    """Resultado de emparejar una película con TMDB: su tmdb_id y match_status.

    Al crearlo se comprueba que tmdb_id sea None si y solo si status es
    not_found; si no, lanza ValueError.
    """

    tmdb_id: int | None
    status: MatchStatus

    def __post_init__(self) -> None:
        if (self.tmdb_id is None) != (self.status == MatchStatus.NOT_FOUND):
            raise ValueError(
                "tmdb_id debe ser None si y solo si status es not_found "
                f"(tmdb_id={self.tmdb_id}, status={self.status})"
            )


def _normalize_title(title: str) -> str:
    """Normaliza un título para compararlo con otros.

    Quita los acentos y otras marcas diacríticas (la ñ pasa a ser n) y lo
    pasa a minúsculas con casefold, que también trata casos como la ß
    alemana. Así "Amélie" y "AMELIE" quedan iguales.
    """
    decomposed = unicodedata.normalize("NFKD", title)
    without_accent = "".join(
        char for char in decomposed if unicodedata.combining(char) == 0
    )
    composed = unicodedata.normalize("NFC", without_accent)
    normalized_title = composed.casefold()
    return normalized_title


def _filter_candidates(
    name: str, results: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Obtiene los resultados de TMDB cuyo título coincide con name.

    Un resultado coincide si su title o su original_title es igual a name
    una vez normalizados los dos con _normalize_title. Devuelve una copia
    de cada resultado que coincide, en el mismo orden.
    """
    normalized_name = _normalize_title(name)
    candidates = [
        dict(candidate)
        for candidate in results
        if (
            _normalize_title(candidate["title"]) == normalized_name
            or _normalize_title(candidate["original_title"]) == normalized_name
        )
    ]
    return candidates


def _decide(candidates: Sequence[Mapping[str, Any]]) -> MatchResult:
    """Elige el tmdb_id y el match_status según los candidatos filtrados.

    Sin candidatos, la película queda como not_found y con tmdb_id None.
    Con uno, como matched. Con varios, como ambiguous, y se elige el que
    tiene más vote_count, es decir, el más popular en TMDB.
    """
    if not candidates:
        return MatchResult(tmdb_id=None, status=MatchStatus.NOT_FOUND)

    best = max(candidates, key=lambda candidate: candidate["vote_count"])
    status = MatchStatus.MATCHED if len(candidates) == 1 else MatchStatus.AMBIGUOUS
    return MatchResult(tmdb_id=best["id"], status=status)


def _filter_by_year(
    candidates: Sequence[Mapping[str, Any]], year: int
) -> list[dict[str, Any]]:
    """Obtiene los candidatos cuyo año de estreno está a ±1 de year"""
    return [
        dict(candidate)
        for candidate in candidates
        if (
            candidate.get("release_date")
            and abs(int(candidate["release_date"][:4]) - year) <= 1
        )
    ]


def match_film(name: str, year: str, search: SearchFunction) -> MatchResult:
    """Busca una película en TMDB y decide su tmdb_id y match_status.

    Primero busca por título y año. Si ningún resultado coincide con el
    título y la película tiene año, repite la búsqueda sin año y se queda
    con los candidatos estrenados como mucho un año antes o después. Si
    hay un candidato, la película queda como matched; si hay varios, como
    ambiguous, con el de más vote_count; y si no hay ninguno, como
    not_found.

    Args:
        name: Título de la película en Letterboxd.
        year: Año de estreno en Letterboxd, o cadena vacía si no tiene.
        search: Función que busca en TMDB por título y año (o None) y
            devuelve la lista de resultados, normalmente
            TMDBClient.search_movies.

    Returns:
        MatchResult con el tmdb_id y el match_status elegidos.

    Raises:
        Exception: Propaga sin capturar las excepciones de search, por
            ejemplo requests.HTTPError si falla la petición a TMDB.
    """
    search_year = year or None
    results = search(name, search_year)
    candidates = _filter_candidates(name, results)
    if not candidates and search_year is not None:
        without_year_results = search(name, None)
        new_candidates = _filter_candidates(name, without_year_results)
        candidates = _filter_by_year(new_candidates, int(search_year))
    return _decide(candidates)
