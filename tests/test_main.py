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
