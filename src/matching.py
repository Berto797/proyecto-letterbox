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
