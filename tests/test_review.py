from collections.abc import Sequence
from pathlib import Path

import pytest

from db import open_connection
from db_helpers import NEWER_LOAD, SELECT_MATCHES, insert_match, insert_watchlist_row
from matching import MatchStatus
from review import ManualMatch, apply_manual_matches, read_manual_matches

VALID_MANUAL_CSV = """letterboxd_uri,tmdb_id
https://boxd.it/jkPq,1204
https://boxd.it/eOCm,320
"""
VALID_MANUAL_EXTRA_COLUMNS_CSV = """letterboxd_uri,tmdb_id,film_name,film_year
https://boxd.it/jkPq,1204,Portrait of a Lady on Fire,2019
https://boxd.it/eOCm,320,Get Out,2017
"""
VALID_MANUAL_SPACES_CSV = """letterboxd_uri,tmdb_id
 https://boxd.it/jkPq , 1204
https://boxd.it/eOCm ,  320
"""
EXPECTED_MATCHES = [
    ManualMatch(letterboxd_uri="https://boxd.it/jkPq", tmdb_id=1204),
    ManualMatch(letterboxd_uri="https://boxd.it/eOCm", tmdb_id=320),
]


def test_read_manual_matches_csv_not_exists(tmp_path: Path) -> None:
    manual_matches_csv = tmp_path / "manual_matches.csv"

    result = read_manual_matches(manual_matches_csv)

    assert result == []


@pytest.mark.parametrize(
    "csv_text, encoding, expected_matches",
    [
        pytest.param(
            VALID_MANUAL_CSV,
            "utf-8",
            EXPECTED_MATCHES,
            id="csv_valid",
        ),
        pytest.param(
            VALID_MANUAL_CSV,
            "utf-8-sig",
            EXPECTED_MATCHES,
            id="csv_valid_bom",
        ),
        pytest.param(
            VALID_MANUAL_EXTRA_COLUMNS_CSV,
            "utf-8",
            EXPECTED_MATCHES,
            id="csv_valid_extra_columns",
        ),
        pytest.param(
            VALID_MANUAL_SPACES_CSV,
            "utf-8",
            EXPECTED_MATCHES,
            id="csv_valid_with_spaces",
        ),
        pytest.param(
            "letterboxd_uri,tmdb_id",
            "utf-8",
            [],
            id="csv_valid_only_headers",
        ),
    ],
)
def test_read_manual_matches_valid(
    tmp_path: Path,
    csv_text: str,
    encoding: str,
    expected_matches: Sequence[ManualMatch],
) -> None:
    manual_matches_csv = tmp_path / "manual_matches.csv"
    manual_matches_csv.write_text(csv_text, encoding=encoding)

    result = read_manual_matches(manual_matches_csv)

    assert result == expected_matches


@pytest.mark.parametrize(
    "csv_text, encoding, expected_error",
    [
        pytest.param(
            "",
            "utf-8",
            "Archivo .* vacío",
            id="file_empty",
        ),
        pytest.param(
            "letterboxd_uri,tmdb_id,film_name\nhttps://boxd.it/jkPq,1204,Amélie\n",
            "latin-1",
            "no está codificado en UTF-8",
            id="file_not_utf8",
        ),
        pytest.param(
            "letterboxd_uri\nhttps://boxd.it/jkPq\n",
            "utf-8",
            "Faltan los encabezados",
            id="missing_tmdb_id_header",
        ),
        pytest.param(
            "letterboxd_uri,tmdb_id\n,1204\n",
            "utf-8",
            "está vacío",
            id="letterboxd_uri_empty",
        ),
        pytest.param(
            "letterboxd_uri,tmdb_id\nhttps://boxd.it/jkPq,\n",
            "utf-8",
            "no es un número entero",
            id="tmdb_id_empty",
        ),
        pytest.param(
            "letterboxd_uri,tmdb_id\nhttps://boxd.it/jkPq\n",
            "utf-8",
            "no es un número entero",
            id="short_row_tmdb_id_none",
        ),
        pytest.param(
            "letterboxd_uri,tmdb_id\nhttps://boxd.it/jkPq,abc\n",
            "utf-8",
            "no es un número entero",
            id="tmdb_id_not_integer",
        ),
        pytest.param(
            "letterboxd_uri,tmdb_id\nhttps://boxd.it/jkPq,0\n",
            "utf-8",
            "tiene que ser positivo",
            id="tmdb_id_zero",
        ),
        pytest.param(
            "letterboxd_uri,tmdb_id\nhttps://boxd.it/jkPq,-1204\n",
            "utf-8",
            "tiene que ser positivo",
            id="tmdb_id_negative",
        ),
        pytest.param(
            "letterboxd_uri,tmdb_id\n"
            "https://boxd.it/jkPq,1204\n"
            "https://boxd.it/jkPq,302\n",
            "utf-8",
            "repetido",
            id="letterboxd_uri_duplicate",
        ),
    ],
)
def test_read_manual_matches_invalid(
    tmp_path: Path, csv_text: str, encoding: str, expected_error: str
) -> None:
    manual_matches_csv = tmp_path / "manual_matches.csv"
    manual_matches_csv.write_text(csv_text, encoding=encoding)

    with pytest.raises(ValueError, match=expected_error):
        read_manual_matches(manual_matches_csv)


def test_apply_manual_matches_saves_manual(clean_db: None, tmp_path: Path) -> None:
    with open_connection() as conn:
        insert_watchlist_row(
            conn,
            "https://boxd.it/aaa",
            "Get Out",
            "2017",
            NEWER_LOAD,
        )
        insert_watchlist_row(
            conn,
            "https://boxd.it/bbb",
            "Todavía",
            "",
            NEWER_LOAD,
        )

    manual_matches_csv = tmp_path / "manual_matches.csv"
    manual_matches_csv.write_text(
        "letterboxd_uri,tmdb_id\nhttps://boxd.it/aaa,1204\nhttps://boxd.it/bbb,302\n",
        encoding="utf-8",
    )

    result = apply_manual_matches(manual_matches_csv)

    with open_connection() as conn:
        rows = conn.execute(SELECT_MATCHES).fetchall()

    assert result == 2
    assert rows == [
        ("https://boxd.it/aaa", 1204, MatchStatus.MANUAL),
        ("https://boxd.it/bbb", 302, MatchStatus.MANUAL),
    ]


def test_apply_manual_matches_replaces_existing_match(
    clean_db: None, tmp_path: Path
) -> None:
    with open_connection() as conn:
        insert_watchlist_row(
            conn,
            "https://boxd.it/aaa",
            "Get Out",
            "2017",
            NEWER_LOAD,
        )
        insert_match(conn, "https://boxd.it/aaa", 1234, MatchStatus.AMBIGUOUS)

    manual_matches_csv = tmp_path / "manual_matches.csv"
    manual_matches_csv.write_text(
        "letterboxd_uri,tmdb_id\nhttps://boxd.it/aaa,1001\n", encoding="utf-8"
    )

    result = apply_manual_matches(manual_matches_csv)

    with open_connection() as conn:
        rows = conn.execute(SELECT_MATCHES).fetchall()

    assert result == 1
    assert rows == [
        ("https://boxd.it/aaa", 1001, MatchStatus.MANUAL),
    ]


def test_apply_manual_matches_unknown_uri(clean_db: None, tmp_path: Path) -> None:
    with open_connection() as conn:
        insert_watchlist_row(
            conn,
            "https://boxd.it/aaa",
            "Get Out",
            "2017",
            NEWER_LOAD,
        )

    manual_matches_csv = tmp_path / "manual_matches.csv"
    manual_matches_csv.write_text(
        "letterboxd_uri,tmdb_id\nhttps://boxd.it/aaa,1204\nhttps://boxd.it/bbb,302\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="no están en la watchlist"):
        apply_manual_matches(manual_matches_csv)

    with open_connection() as conn:
        rows = conn.execute(SELECT_MATCHES).fetchall()

    assert rows == []


def test_apply_manual_matches_file_not_exists(tmp_path: Path) -> None:
    manual_matches_csv = tmp_path / "manual_matches.csv"

    result = apply_manual_matches(manual_matches_csv)

    assert result == 0
