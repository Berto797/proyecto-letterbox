# CLAUDE.md

Instructions for Claude Code when working in this repository. The project itself is described in `README.md`.

## Conventions

Follow the project's coding conventions:

@docs/conventions.md

## Commands

Run everything from the repository root, with the virtual environment active (`source .venv/bin/activate`).

```bash
ruff check .            # lint: line length, import order, docstrings
ruff format .           # format
mypy                    # types, strict mode (src/ and tests/)
pytest                  # all tests; Docker must be running for the integration tests
docker compose up -d    # development database (letterbox-db)
python src/main.py      # full pipeline; --match-only (-m) skips the CSV load
```

Before saying that a change is finished, run `ruff check .`, `ruff format --check .`, `mypy` and `pytest`, and report the result.

## Rules

- Do not commit, push or open pull requests unless asked to.
- Never commit `.env`, the contents of `data/input/` and `data/processed/`, `data/manual_matches.csv` or `data/review/`.
- Tests must never call the real TMDB API, read `.env` or use the development database.
- Ask before running the pipeline against the development database: it changes its data and may call the TMDB API.
- Ask before adding a dependency.
- When a convention changes, update `docs/conventions.md` in the same change.
