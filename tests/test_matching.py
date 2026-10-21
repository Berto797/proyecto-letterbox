import pytest

from matching import normalize_title


@pytest.mark.parametrize(
    "title, expected_title",
    [
        pytest.param("parasite", "parasite", id="unchanged"),
        pytest.param("PARASITE", "parasite", id="uppercase"),
        pytest.param("Sirāt", "sirat", id="macron"),
        pytest.param("Todavía", "todavia", id="acute_accent"),
        pytest.param("Straße", "strasse", id="sharp_s"),
        pytest.param("기생충", "기생충", id="non_latin"),
    ],
)
def test_normalize_title(title: str, expected_title: str) -> None:
    result = normalize_title(title)

    assert result == expected_title
