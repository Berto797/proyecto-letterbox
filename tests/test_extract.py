import pytest

from extract import _extract_csv

VALID_CSV = """Date,Name,Year,Letterboxd URI
2026-01-01,Portrait of a Lady on Fire,2019,https://boxd.it/jkPq
2026-01-01,Get Out,2017,https://boxd.it/eOCm
2026-01-01,Call Me by Your Name,2017,https://boxd.it/dYmm
2026-01-01,The Handmaiden,2016,https://boxd.it/948A
"""
EXTRA_COLUMNS_CSV = """Date,Name,Year,Letterboxd URI,Score
2026-01-01,Portrait of a Lady on Fire,2019,https://boxd.it/jkPq,87
2026-01-01,Get Out,2017,https://boxd.it/eOCm,80
2026-01-01,Call Me by Your Name,2017,https://boxd.it/dYmm,82
2026-01-01,The Handmaiden,2016,https://boxd.it/948A,75
"""


def test_extract_csv_valid_file(tmp_path):
    csv_file = tmp_path / "watchlist.csv"
    csv_file.write_text(VALID_CSV, encoding="utf-8")

    film_list = _extract_csv(csv_file)

    assert len(film_list) == 4
    assert film_list[0]["Name"] == "Portrait of a Lady on Fire"
    assert film_list[0]["Year"] == "2019"


def test_extract_csv_with_bom(tmp_path):
    csv_file = tmp_path / "watchlist.csv"
    csv_file.write_text(VALID_CSV, encoding="utf-8-sig")

    film_list = _extract_csv(csv_file)

    assert len(film_list) == 4
    assert film_list[0]["Name"] == "Portrait of a Lady on Fire"
    assert film_list[0]["Year"] == "2019"


def test_extract_csv_empty_file(tmp_path):
    csv_file = tmp_path / "watchlist.csv"
    csv_file.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="vacío"):
        _extract_csv(csv_file)


def test_extract_csv_missing_headers(tmp_path):
    csv_file = tmp_path / "watchlist.csv"
    csv_file.write_text(
        "Date,Name,Letterboxd URI\n2026-01-01,Amélie,x\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="Faltan los encabezados"):
        _extract_csv(csv_file)


def test_extract_csv_no_films(tmp_path):
    csv_file = tmp_path / "watchlist.csv"
    csv_file.write_text("""Date,Name,Year,Letterboxd URI\n""", encoding="utf-8")

    with pytest.raises(ValueError, match="No se han encontrado películas"):
        _extract_csv(csv_file)


def test_extract_csv_wrong_encoding(tmp_path):
    csv_file = tmp_path / "watchlist.csv"
    csv_file.write_text(
        "Date,Name,Year,Letterboxd URI\n2026-01-01,Amélie,2001,x\n", encoding="latin-1"
    )

    with pytest.raises(ValueError, match="UTF-8"):
        _extract_csv(csv_file)


def test_extract_csv_extra_columns(tmp_path):
    csv_file = tmp_path / "watchlist.csv"
    csv_file.write_text(EXTRA_COLUMNS_CSV, encoding="utf-8")

    film_list = _extract_csv(csv_file)

    assert len(film_list) == 4
    assert film_list[0]["Name"] == "Portrait of a Lady on Fire"
    assert film_list[0]["Year"] == "2019"
    assert film_list[0]["Score"] == "87"
