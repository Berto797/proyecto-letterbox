import unicodedata
from collections.abc import Callable, Mapping, Sequence
from typing import Any


def normalize_title(title: str) -> str:
    """Normaliza un título para compararlo: sin acentos y en minúsculas"""
    decomposed = unicodedata.normalize("NFKD", title)
    without_accent = "".join(
        char for char in decomposed if unicodedata.combining(char) == 0
    )
    composed = unicodedata.normalize("NFC", without_accent)
    normalized_title = composed.casefold()
    return normalized_title


def filter_candidates(
    name: str, results: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Obtiene los resultados cuyo title u original_title coincide con name, una vez normalizados"""
    normalized_name = normalize_title(name)
    candidates = [
        dict(candidate)
        for candidate in results
        if (
            normalize_title(candidate["title"]) == normalized_name
            or normalize_title(candidate["original_title"]) == normalized_name
        )
    ]
    return candidates


def decide(candidates: Sequence[Mapping[str, Any]]) -> tuple[int | None, str]:
    """Elige el tmdb_id y el match_status según los candidatos filtrados"""
    if not candidates:
        return (None, "not_found")

    best = max(candidates, key=lambda candidate: candidate["vote_count"])
    status = "matched" if len(candidates) == 1 else "ambiguous"
    return (best["id"], status)


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


def match_film(
    name: str, year: str, search: Callable[[str, str | None], list[dict[str, Any]]]
) -> tuple[int | None, str]:
    """Busca una película en TMDB y decide su tmdb_id y match_status"""
    search_year = year or None
    results = search(name, search_year)
    candidates = filter_candidates(name, results)
    if not candidates and search_year is not None:
        without_year_results = search(name, None)
        new_candidates = filter_candidates(name, without_year_results)
        candidates = _filter_by_year(new_candidates, int(search_year))
    return decide(candidates)
