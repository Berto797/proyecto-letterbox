import psycopg
import pytest

import extract
import main

VALID_CSV = """Date,Name,Year,Letterboxd URI
2026-01-01,Get Out,2017,https://boxd.it/eOCm
2026-01-01,The Handmaiden,2016,https://boxd.it/948A
"""


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
def test_main_valid(tmp_path, monkeypatch, capsys, args, original_should_exist):
    input_dir = tmp_path / "input"
    processed_dir = tmp_path / "processed"
    input_dir.mkdir()
    processed_dir.mkdir()
    csv_file = input_dir / "watchlist.csv"
    csv_file.write_text(VALID_CSV, encoding="utf-8")
    monkeypatch.setattr(extract, "INPUT_DIR", input_dir)
    monkeypatch.setattr(extract, "PROCESSED_DIR", processed_dir)

    def fake_load_raw(csv_processed_path, film_list):
        pass

    monkeypatch.setattr(main, "load_raw", fake_load_raw)

    main.main(args)

    processed_files = list(processed_dir.glob("watchlist_*.csv"))
    assert csv_file.exists() == original_should_exist
    assert len(processed_files) == 1
    assert processed_files[0].read_text(encoding="utf-8") == VALID_CSV
    captured = capsys.readouterr()
    assert "Se han cargado 2 películas" in captured.out
    assert captured.err == ""


def test_main_invalid(tmp_path, monkeypatch, capsys):
    input_dir = tmp_path / "input"
    processed_dir = tmp_path / "processed"
    input_dir.mkdir()
    processed_dir.mkdir()
    csv_file = input_dir / "watchlist.csv"
    csv_file.write_text(VALID_CSV, encoding="utf-8")
    monkeypatch.setattr(extract, "INPUT_DIR", input_dir)
    monkeypatch.setattr(extract, "PROCESSED_DIR", processed_dir)

    def fake_load_raw(csv_processed_path, film_list):
        raise psycopg.OperationalError("connection failed")

    monkeypatch.setattr(main, "load_raw", fake_load_raw)

    with pytest.raises(SystemExit) as exc_info:
        main.main([])

    processed_files = list(processed_dir.glob("watchlist_*.csv"))
    assert exc_info.value.code == 1
    assert csv_file.exists()
    assert len(processed_files) == 0
    captured = capsys.readouterr()
    assert "El pipeline no se ha completado" in captured.err
    assert "connection failed" in captured.err
    assert captured.out == ""
