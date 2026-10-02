import pytest

from extract import _extract_csv, _get_csv_files

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


@pytest.mark.parametrize(
    "encoding",
    [
        pytest.param("utf-8", id="no_bom"),
        pytest.param("utf-8-sig", id="with_bom"),
    ],
)
def test_extract_csv_valid_file(tmp_path, encoding):
    csv_file = tmp_path / "watchlist.csv"
    csv_file.write_text(VALID_CSV, encoding=encoding)

    film_list = _extract_csv(csv_file)

    assert len(film_list) == 4
    assert film_list[0]["Name"] == "Portrait of a Lady on Fire"
    assert film_list[0]["Year"] == "2019"


@pytest.mark.parametrize(
    "content, encoding, expected_error",
    [
        pytest.param(
            "",
            "utf-8",
            "vacío",
            id="empty_file",
        ),
        pytest.param(
            "Date,Name,Letterboxd URI\n2026-01-01,Amélie,x\n",
            "utf-8",
            "Faltan los encabezados",
            id="missing_headers",
        ),
        pytest.param(
            "Date,Name,Year,Letterboxd URI\n",
            "utf-8",
            "No se han encontrado películas",
            id="no_films",
        ),
        pytest.param(
            "Date,Name,Year,Letterboxd URI\n2026-01-01,Amélie,2001,x\n",
            "latin-1",
            "UTF-8",
            id="wrong_encoding",
        ),
    ],
)
def test_extract_csv_invalid_file(tmp_path, content, encoding, expected_error):
    csv_file = tmp_path / "watchlist.csv"
    csv_file.write_text(content, encoding=encoding)

    with pytest.raises(ValueError, match=expected_error):
        _extract_csv(csv_file)


def test_extract_csv_extra_columns(tmp_path):
    csv_file = tmp_path / "watchlist.csv"
    csv_file.write_text(EXTRA_COLUMNS_CSV, encoding="utf-8")

    film_list = _extract_csv(csv_file)

    assert len(film_list) == 4
    assert film_list[0]["Name"] == "Portrait of a Lady on Fire"
    assert film_list[0]["Year"] == "2019"
    assert film_list[0]["Score"] == "87"


@pytest.mark.parametrize(
    "files_to_create, expected_files",
    [
        pytest.param(
            ["watchlist.csv"],
            ["watchlist.csv"],
            id="single_csv",
        ),
        pytest.param(
            ["watchlist.csv", "notes.txt", ".gitkeep"],
            ["watchlist.csv"],
            id="csv_and_other_files",
        ),
        pytest.param(
            ["watchlist_1.csv", "watchlist_2.csv"],
            ["watchlist_1.csv", "watchlist_2.csv"],
            id="two_csv",
        ),
        pytest.param(
            ["WATCHLIST.CSV"],
            [],
            id="uppercase_extension",
        ),
        pytest.param(
            [],
            [],
            id="empty_folder",
        ),
    ],
)
def test_get_csv_files(tmp_path, files_to_create, expected_files):
    for file_name in files_to_create:
        (tmp_path / file_name).touch()

    csv_files = _get_csv_files(tmp_path)

    assert sorted(path.name for path in csv_files) == sorted(expected_files)


def test_get_csv_files_csv_wrong_path(tmp_path):
    input_path = tmp_path / "input"
    csv_file = tmp_path / "watchlist.csv"
    input_path.mkdir()
    csv_file.touch()

    csv_files = _get_csv_files(input_path)

    assert csv_files == []
