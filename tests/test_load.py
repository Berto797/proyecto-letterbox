from pathlib import Path

import pytest

from load import _build_row

FILM = {
    "Date": "2026-01-01",
    "Name": "Get Out",
    "Year": "2017",
    "Letterboxd URI": "https://boxd.it/eOCm",
}
CSV_PROCESSED_PATH = Path("processed/watchlist_20260101_00_00_00.csv")
EXPECTED_ROW = {
    "watchlisted_at": "2026-01-01",
    "film_name": "Get Out",
    "film_year": "2017",
    "letterboxd_uri": "https://boxd.it/eOCm",
    "source_file": "watchlist_20260101_00_00_00.csv",
}


@pytest.mark.parametrize(
    "film, expected_extras",
    [
        pytest.param(
            FILM,
            {},
            id="no_extras",
        ),
        pytest.param(
            {**FILM, "Score": "87"},
            {"Score": "87"},
            id="one_extra_column",
        ),
        pytest.param(
            {**FILM, "Score": "87", "Rating": "4.5"},
            {"Score": "87", "Rating": "4.5"},
            id="several_extra_columns",
        ),
        pytest.param(
            {**FILM, None: ["valor1", "valor2"]},
            {None: ["valor1", "valor2"]},
            id="extra_values_without_header",
        ),
    ],
)
def test_build_row(film, expected_extras):
    row = _build_row(CSV_PROCESSED_PATH, film)

    extra_fields = row.pop("extra_fields")
    assert extra_fields.obj == expected_extras
    assert row == EXPECTED_ROW
