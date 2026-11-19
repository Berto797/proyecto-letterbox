from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import NoReturn

import psycopg
import pytest
import requests

import extract
import main
from matching import MatchStatus, SearchFunction

VALID_CSV = """Date,Name,Year,Letterboxd URI
2026-01-01,Get Out,2017,https://boxd.it/eOCm
2026-01-01,The Handmaiden,2016,https://boxd.it/948A
"""


@pytest.fixture(autouse=True)
def fake_review(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Sustituye los pasos de revisión manual por versiones falsas en todos los tests.

    Se aplica automáticamente a todos los tests de este archivo para que
    ninguno toque PostgreSQL ni lea o escriba archivos. Las funciones
    falsas devuelven 0 y apuntan cada llamada ("apply" o "write") en la
    lista que devuelve la fixture, para comprobar qué pasos se ejecutan y
    en qué orden.
    """
    steps: list[str] = []

    def fake_apply_manual_matches(path: Path) -> int:
        steps.append("apply")
        return 0

    def fake_write_review_file(path: Path) -> int:
        steps.append("write")
        return 0

    monkeypatch.setattr(main, "apply_manual_matches", fake_apply_manual_matches)
    monkeypatch.setattr(main, "write_review_file", fake_write_review_file)

    return steps


@pytest.fixture
def fake_match(monkeypatch: pytest.MonkeyPatch) -> list[SearchFunction]:
    """Sustituye el emparejamiento por uno falso que apunta cada llamada, sin TMDB"""
    monkeypatch.setenv("TMDB_TOKEN", "fake-token")
    calls: list[SearchFunction] = []

    def fake_match_pending_films(search: SearchFunction) -> Counter[MatchStatus]:
        calls.append(search)
        return Counter({MatchStatus.MATCHED: 2})

    monkeypatch.setattr(main, "match_pending_films", fake_match_pending_films)

    return calls


@pytest.mark.parametrize(
    "args, original_should_exist",
    [
        pytest.param(
            [],
            False,
            id="move",
        ),
        pytest.param(
            ["--keep-original"],
            True,
            id="keep_original_long",
        ),
        pytest.param(
            ["-k"],
            True,
            id="keep_original_short",
        ),
    ],
)
def test_main_valid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fake_match: list[SearchFunction],
    args: Sequence[str],
    original_should_exist: bool,
) -> None:
    input_dir = tmp_path / "input"
    processed_dir = tmp_path / "processed"
    input_dir.mkdir()
    processed_dir.mkdir()
    csv_file = input_dir / "watchlist.csv"
    csv_file.write_text(VALID_CSV, encoding="utf-8")
    monkeypatch.setattr(extract, "INPUT_DIR", input_dir)
    monkeypatch.setattr(extract, "PROCESSED_DIR", processed_dir)

    def fake_load_raw(
        csv_processed_path: Path, film_list: Sequence[Mapping[str, str]]
    ) -> None:
        pass

    monkeypatch.setattr(main, "load_raw", fake_load_raw)

    main.main(args)

    processed_files = list(processed_dir.glob("watchlist_*.csv"))
    assert csv_file.exists() == original_should_exist
    assert len(processed_files) == 1
    assert processed_files[0].read_text(encoding="utf-8") == VALID_CSV
    assert len(fake_match) == 1
    captured = capsys.readouterr()
    assert "Se han cargado 2 películas" in captured.out
    assert "Se han emparejado 2 películas: matched 2" in captured.out
    assert captured.err == ""


def test_main_load_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fake_match: list[SearchFunction],
) -> None:
    input_dir = tmp_path / "input"
    processed_dir = tmp_path / "processed"
    input_dir.mkdir()
    processed_dir.mkdir()
    csv_file = input_dir / "watchlist.csv"
    csv_file.write_text(VALID_CSV, encoding="utf-8")
    monkeypatch.setattr(extract, "INPUT_DIR", input_dir)
    monkeypatch.setattr(extract, "PROCESSED_DIR", processed_dir)

    def fake_load_raw(
        csv_processed_path: Path, film_list: Sequence[Mapping[str, str]]
    ) -> NoReturn:
        raise psycopg.OperationalError("connection failed")

    monkeypatch.setattr(main, "load_raw", fake_load_raw)

    with pytest.raises(SystemExit) as exc_info:
        main.main([])

    processed_files = list(processed_dir.glob("watchlist_*.csv"))
    assert exc_info.value.code == 1
    assert csv_file.exists()
    assert len(processed_files) == 0
    assert fake_match == []
    captured = capsys.readouterr()
    assert "El pipeline no se ha completado" in captured.err
    assert "connection failed" in captured.err
    assert captured.out == ""


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(
            ["--match-only"],
            id="match_only_long",
        ),
        pytest.param(
            ["-m"],
            id="match_only_short",
        ),
    ],
)
def test_main_match_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fake_match: list[SearchFunction],
    args: Sequence[str],
) -> None:
    input_dir = tmp_path / "input"
    processed_dir = tmp_path / "processed"
    input_dir.mkdir()
    processed_dir.mkdir()
    csv_file = input_dir / "watchlist.csv"
    csv_file.write_text(VALID_CSV, encoding="utf-8")
    monkeypatch.setattr(extract, "INPUT_DIR", input_dir)
    monkeypatch.setattr(extract, "PROCESSED_DIR", processed_dir)

    def fake_load_raw(
        csv_processed_path: Path, film_list: Sequence[Mapping[str, str]]
    ) -> NoReturn:
        raise AssertionError("no debería llamarse con --match-only")

    monkeypatch.setattr(main, "load_raw", fake_load_raw)

    main.main(args)

    processed_files = list(processed_dir.glob("watchlist_*.csv"))
    assert csv_file.exists()
    assert len(processed_files) == 0
    assert len(fake_match) == 1
    captured = capsys.readouterr()
    assert "Se han cargado" not in captured.out
    assert "Se han emparejado 2 películas: matched 2" in captured.out
    assert captured.err == ""


def test_main_no_pending_films(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("TMDB_TOKEN", "fake-token")
    monkeypatch.setattr(main, "match_pending_films", lambda search: Counter())

    main.main(["-m"])

    captured = capsys.readouterr()
    assert "No hay películas pendientes de emparejar" in captured.out
    assert captured.err == ""


def test_main_tmdb_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("TMDB_TOKEN", "fake-token")

    def fake_match_pending_films(search: SearchFunction) -> NoReturn:
        raise requests.HTTPError("401")

    monkeypatch.setattr(main, "match_pending_films", fake_match_pending_films)

    with pytest.raises(SystemExit) as exc_info:
        main.main(["-m"])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "El pipeline no se ha completado" in captured.err
    assert "401" in captured.err
    assert captured.out == ""


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(
            None,
            id="none_token",
        ),
        pytest.param(
            "",
            id="empty_token",
        ),
    ],
)
def test_main_missing_token(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fake_match: list[SearchFunction],
    token: str | None,
) -> None:
    if token is None:
        monkeypatch.delenv("TMDB_TOKEN", raising=False)
    else:
        monkeypatch.setenv("TMDB_TOKEN", token)

    with pytest.raises(SystemExit) as exc_info:
        main.main(["-m"])

    assert exc_info.value.code == 1
    assert fake_match == []
    captured = capsys.readouterr()
    assert "El pipeline no se ha completado" in captured.err
    assert "Falta TMDB_TOKEN" in captured.err
    assert captured.out == ""


def test_main_steps_order(
    monkeypatch: pytest.MonkeyPatch, fake_review: list[str]
) -> None:
    monkeypatch.setenv("TMDB_TOKEN", "fake-token")

    def fake_match_pending_films(search: SearchFunction) -> Counter[MatchStatus]:
        fake_review.append("match")
        return Counter()

    monkeypatch.setattr(main, "match_pending_films", fake_match_pending_films)

    main.main(["-m"])

    assert fake_review == ["apply", "match", "write"]


@pytest.mark.parametrize(
    "applied_count, films_count, expected_lines, unexpected_text",
    [
        pytest.param(
            3,
            18,
            [
                "Se han aplicado 3 emparejamientos manuales",
                "Hay 18 películas por revisar en data/review/pending_matches.csv",
            ],
            None,
            id="with_counts",
        ),
        pytest.param(
            0,
            0,
            ["No hay películas que revisar"],
            "emparejamientos manuales",
            id="zero_counts",
        ),
    ],
)
def test_main_review_messages(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fake_match: list[SearchFunction],
    applied_count: int,
    films_count: int,
    expected_lines: Sequence[str],
    unexpected_text: str | None,
) -> None:
    monkeypatch.setattr(main, "apply_manual_matches", lambda path: applied_count)
    monkeypatch.setattr(main, "write_review_file", lambda path: films_count)

    main.main(["-m"])

    captured = capsys.readouterr()
    for line in expected_lines:
        assert line in captured.out
    if unexpected_text is not None:
        assert unexpected_text not in captured.out
    assert captured.err == ""


def test_main_manual_matches_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fake_review: list[str],
    fake_match: list[SearchFunction],
) -> None:
    def fake_apply_manual_matches(path: Path) -> NoReturn:
        raise ValueError(
            "Los letterboxd_uri https://boxd.it/zzz de manual_matches.csv "
            "no están en la watchlist"
        )

    monkeypatch.setattr(main, "apply_manual_matches", fake_apply_manual_matches)

    with pytest.raises(SystemExit) as exc_info:
        main.main(["-m"])

    assert exc_info.value.code == 1
    assert fake_match == []
    assert "write" not in fake_review
    captured = capsys.readouterr()
    assert "El pipeline no se ha completado" in captured.err
    assert "no están en la watchlist" in captured.err


def test_main_review_file_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fake_match: list[SearchFunction],
) -> None:
    def fake_write_review_file(path: Path) -> NoReturn:
        raise PermissionError("Permission denied: 'pending_matches.csv'")

    monkeypatch.setattr(main, "write_review_file", fake_write_review_file)

    with pytest.raises(SystemExit) as exc_info:
        main.main(["-m"])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "El pipeline no se ha completado" in captured.err
    assert "Permission denied" in captured.err
