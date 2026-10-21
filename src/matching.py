import unicodedata
from collections.abc import Mapping, Sequence
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
