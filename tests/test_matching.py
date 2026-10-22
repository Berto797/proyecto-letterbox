from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from matching import (
    _filter_by_year,
    decide,
    filter_candidates,
    match_film,
    normalize_title,
)

RAY = {"id": 1, "title": "Ray", "original_title": "Ray"}
OTHER_RAY = {"id": 2, "title": "Ray", "original_title": "Ray"}
DISTRICT_B13 = {"id": 3, "title": "District B13", "original_title": "Banlieue 13"}
PARASITE = {"id": 4, "title": "Parasite", "original_title": "기생충"}
SIRAT = {"id": 5, "title": "Sirāt", "original_title": "Sirāt"}
FEW_VOTES = {"id": 10, "vote_count": 50}
MANY_VOTES = {"id": 11, "vote_count": 900}
TIED_MANY_VOTES = {"id": 12, "vote_count": 900}
FILM_2016 = {
    "id": 20,
    "title": "Film",
    "original_title": "Film",
    "release_date": "2016-05-12",
    "vote_count": 300,
}
FILM_2017 = {
    "id": 21,
    "title": "Film",
    "original_title": "Film",
    "release_date": "2017-03-01",
    "vote_count": 100,
}
FILM_2018 = {
    "id": 22,
    "title": "Film",
    "original_title": "Film",
    "release_date": "2018-01-20",
    "vote_count": 500,
}
FILM_1985 = {
    "id": 23,
    "title": "Film",
    "original_title": "Film",
    "release_date": "1985-06-01",
    "vote_count": 900,
}
OTHER_FILM_2017 = {
    "id": 24,
    "title": "Other Film",
    "original_title": "Other Film",
    "release_date": "2017-03-01",
    "vote_count": 50,
}


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


@pytest.mark.parametrize(
    "release_date, expected_kept",
    [
        pytest.param("2017-03-01", True, id="same_year"),
        pytest.param("2016-05-12", True, id="one_year_before"),
        pytest.param("2018-01-20", True, id="one_year_after"),
        pytest.param("2015-12-31", False, id="two_years_before"),
        pytest.param("1985-06-01", False, id="far_year"),
        pytest.param("", False, id="empty_date"),
        pytest.param(None, False, id="null_date"),
    ],
)
def test_filter_by_year(release_date: str | None, expected_kept: bool) -> None:
    candidate = {"id": 1, "release_date": release_date}
    expected = [candidate] if expected_kept else []

    result = _filter_by_year([candidate], 2017)

    assert result == expected


@pytest.mark.parametrize(
    "year, responses, expected_decision, expected_calls",
    [
        pytest.param(
            "2017",
            {"2017": [FILM_2017]},
            (21, "matched"),
            [("Film", "2017")],
            id="found_with_year",
        ),
        pytest.param(
            "2017",
            {"2017": [], None: [FILM_2016]},
            (20, "matched"),
            [("Film", "2017"), ("Film", None)],
            id="retry_finds_nearby_year",
        ),
        pytest.param(
            "2017",
            {"2017": [], None: [FILM_1985]},
            (None, "not_found"),
            [("Film", "2017"), ("Film", None)],
            id="retry_rejects_far_year",
        ),
        pytest.param(
            "2017",
            {"2017": [OTHER_FILM_2017], None: [OTHER_FILM_2017, FILM_2016]},
            (20, "matched"),
            [("Film", "2017"), ("Film", None)],
            id="retry_after_title_filter",
        ),
        pytest.param(
            "2017",
            {"2017": [], None: [FILM_2016, FILM_1985, FILM_2018]},
            (22, "ambiguous"),
            [("Film", "2017"), ("Film", None)],
            id="retry_several_nearby",
        ),
        pytest.param(
            "",
            {None: [FILM_2016, FILM_2018]},
            (22, "ambiguous"),
            [("Film", None)],
            id="no_year_ambiguous",
        ),
        pytest.param(
            "",
            {None: []},
            (None, "not_found"),
            [("Film", None)],
            id="no_year_not_found",
        ),
    ],
)
def test_match_film(
    year: str,
    responses: Mapping[str | None, list[dict[str, Any]]],
    expected_decision: tuple[int | None, str],
    expected_calls: Sequence[tuple[str, str | None]],
) -> None:
    calls: list[tuple[str, str | None]] = []

    def fake_search(title: str, search_year: str | None) -> list[dict[str, Any]]:
        calls.append((title, search_year))
        return responses[search_year]

    result = match_film("Film", year, fake_search)

    assert result == expected_decision
    assert calls == expected_calls
