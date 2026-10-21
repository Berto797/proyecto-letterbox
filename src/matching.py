import unicodedata


def normalize_title(title: str) -> str:
    """Normaliza un título para compararlo: sin acentos y en minúsculas"""
    decomposed = unicodedata.normalize("NFKD", title)
    without_accent = "".join(
        char for char in decomposed if unicodedata.combining(char) == 0
    )
    composed = unicodedata.normalize("NFC", without_accent)
    normalized_title = composed.casefold()
    return normalized_title
