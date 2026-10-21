from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from matching import decide, filter_candidates, normalize_title

RAY = {"id": 1, "title": "Ray", "original_title": "Ray"}
OTHER_RAY = {"id": 2, "title": "Ray", "original_title": "Ray"}
DISTRICT_B13 = {"id": 3, "title": "District B13", "original_title": "Banlieue 13"}
PARASITE = {"id": 4, "title": "Parasite", "original_title": "기생충"}
SIRAT = {"id": 5, "title": "Sirāt", "original_title": "Sirāt"}
FEW_VOTES = {"id": 10, "vote_count": 50}
MANY_VOTES = {"id": 11, "vote_count": 900}
TIED_MANY_VOTES = {"id": 12, "vote_count": 900}


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


@pytest.mark.parametrize(
    "name, results, expected_candidates",
    [
        pytest.param("Ray", [RAY, DISTRICT_B13], [RAY], id="title_match"),
        pytest.param("기생충", [PARASITE], [PARASITE], id="original_title_match"),
        pytest.param("SIRAT", [SIRAT], [SIRAT], id="normalized_match"),
        pytest.param("Ray", [DISTRICT_B13], [], id="no_match"),
        pytest.param(
            "Ray",
            [RAY, DISTRICT_B13, OTHER_RAY],
            [RAY, OTHER_RAY],
            id="several_matches",
        ),
        pytest.param("Ray", [], [], id="empty_results"),
    ],
)
def test_filter_candidates(
    name: str,
    results: Sequence[Mapping[str, Any]],
    expected_candidates: Sequence[Mapping[str, Any]],
) -> None:
    result = filter_candidates(name, results)

    assert result == expected_candidates


@pytest.mark.parametrize(
    "candidates, expected_decision",
    [
        pytest.param([], (None, "not_found"), id="no_candidates"),
        pytest.param([FEW_VOTES], (10, "matched"), id="single_candidate"),
        pytest.param(
            [FEW_VOTES, MANY_VOTES], (11, "ambiguous"), id="several_candidates"
        ),
        pytest.param(
            [FEW_VOTES, MANY_VOTES, TIED_MANY_VOTES], (11, "ambiguous"), id="tie"
        ),
    ],
)
def test_decide(
    candidates: Sequence[Mapping[str, Any]],
    expected_decision: tuple[int | None, str],
) -> None:
    result = decide(candidates)

    assert result == expected_decision
