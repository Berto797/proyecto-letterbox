from datetime import UTC, datetime
from pathlib import Path

import pytest

import extract
from extract import (
    TIMESTAMP_FORMAT,
    _extract_csv,
    _get_csv_files,
    _get_single_csv,
    define_processed_name,
    move_to_processed,
)

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
EXPECTED_FILMS = [
    {
        "Date": "2026-01-01",
        "Name": "Portrait of a Lady on Fire",
        "Year": "2019",
        "Letterboxd URI": "https://boxd.it/jkPq",
    },
    {
        "Date": "2026-01-01",
        "Name": "Get Out",
        "Year": "2017",
        "Letterboxd URI": "https://boxd.it/eOCm",
    },
    {
        "Date": "2026-01-01",
        "Name": "Call Me by Your Name",
        "Year": "2017",
        "Letterboxd URI": "https://boxd.it/dYmm",
    },
    {
        "Date": "2026-01-01",
        "Name": "The Handmaiden",
        "Year": "2016",
        "Letterboxd URI": "https://boxd.it/948A",
    },
]


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

    assert film_list == EXPECTED_FILMS


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
    scores = ["87", "80", "82", "75"]
    expected = [
        {**film, "Score": score}
        for film, score in zip(EXPECTED_FILMS, scores, strict=True)
    ]

    film_list = _extract_csv(csv_file)

    assert film_list == expected


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


@pytest.mark.parametrize(
    "csv_names, expected_error, expected_exception",
    [
        pytest.param(
            [],
            "ningún CSV",
            FileNotFoundError,
            id="empty_list",
        ),
        pytest.param(
            ["watchlist_1.csv", "watchlist_2.csv"],
            "Se esperaba 1 archivo CSV",
            ValueError,
            id="two_csv",
        ),
    ],
)
def test_get_single_csv_invalid(csv_names, expected_error, expected_exception):
    csv_files = [Path(name) for name in csv_names]

    with pytest.raises(expected_exception, match=expected_error):
        _get_single_csv(Path("input"), csv_files)


def test_get_single_csv_single_csv():
    csv_file = Path("watchlist.csv")

    result = _get_single_csv(Path("input"), [csv_file])

    assert result == csv_file


def test_define_processed_name_valid(monkeypatch):
    processed_dir = Path("processed")
    csv_file = Path("watchlist.csv")
    monkeypatch.setattr(extract, "PROCESSED_DIR", processed_dir)

    result = define_processed_name(csv_file)

    assert not result.exists()
    assert result.parent == processed_dir
    assert result.name.startswith("watchlist_")
    assert result.name.endswith(".csv")
    timestamp = result.name.removeprefix("watchlist_").removesuffix(".csv")
    datetime.strptime(timestamp, TIMESTAMP_FORMAT).replace(tzinfo=UTC)


@pytest.mark.parametrize(
    "keep_original, original_should_exist",
    [
        pytest.param(
            True,
            True,
            id="keep_original",
        ),
        pytest.param(
            False,
            False,
            id="no_keep_original",
        ),
    ],
)
def test_move_to_processed_valid(tmp_path, keep_original, original_should_exist):
    input_dir = tmp_path / "input"
    processed_dir = tmp_path / "processed"
    input_dir.mkdir()
    processed_dir.mkdir()
    csv_file = input_dir / "watchlist.csv"
    csv_file.write_text("test", encoding="utf-8")
    csv_processed_path = processed_dir / "watchlist_test.csv"

    move_to_processed(csv_file, csv_processed_path, keep_original=keep_original)

    assert csv_file.exists() == original_should_exist
    assert csv_processed_path.exists()
    assert csv_processed_path.read_text(encoding="utf-8") == "test"


@pytest.mark.parametrize(
    "keep_original",
    [
        pytest.param(
            True,
            id="keep_original_no_processed_dir",
        ),
        pytest.param(
            False,
            id="no_keep_original_no_processed_dir",
        ),
    ],
)
def test_move_to_processed_invalid(tmp_path, keep_original):
    input_dir = tmp_path / "input"
    processed_dir = tmp_path / "processed"
    input_dir.mkdir()
    csv_file = input_dir / "watchlist.csv"
    csv_file.write_text("test", encoding="utf-8")
    csv_processed_path = processed_dir / "watchlist_test.csv"

    with pytest.raises(OSError):
        move_to_processed(csv_file, csv_processed_path, keep_original=keep_original)
    assert csv_file.exists()


def test_extract_valid(tmp_path, monkeypatch):
    csv_file = tmp_path / "watchlist.csv"
    csv_file.write_text(VALID_CSV, encoding="utf-8")
    monkeypatch.setattr(extract, "INPUT_DIR", tmp_path)

    result_file, film_list = extract.extract()

    assert result_file == csv_file
    assert film_list == EXPECTED_FILMS


# Los casos de error ya se prueban en _get_single_csv y _extract_csv.
# Aquí solo se comprueba que los errores se propagan hasta extract().
def test_extract_invalid(tmp_path, monkeypatch):
    monkeypatch.setattr(extract, "INPUT_DIR", tmp_path)

    with pytest.raises(FileNotFoundError, match="ningún CSV"):
        extract.extract()
