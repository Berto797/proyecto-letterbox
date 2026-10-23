# proyecto-letterbox

A data pipeline that loads a [Letterboxd](https://letterboxd.com/) watchlist export into PostgreSQL, as the first step towards enriching it with data from [TMDB](https://www.themoviedb.org/).

> **Status:** work in progress. Extraction and loading into the raw layer are working. The TMDB client and the title-matching logic are implemented and tested, but not yet connected to the pipeline.

## How it works

`src/main.py` runs the whole pipeline:

```
data/input/watchlist.csv
        │
        ▼
   extract  ──  finds the CSV, validates it and reads its rows
        │
        ▼
     load   ──  inserts every row into raw_watchlist (single transaction)
        │
        ▼
data/processed/watchlist_<timestamp>.csv   (only after a successful load)
```

## Tech stack

- Python 3.14
- PostgreSQL 17 (Docker Compose)
- psycopg 3
- requests (TMDB API)
- pytest, testcontainers (integration tests)
- Ruff (linting and formatting)
- mypy (static type checking, strict mode)
- pre-commit (Git hooks)
- GitHub Actions (CI)

## Project structure

```
├── .github/workflows/  # CI: Ruff, mypy and pytest on every pull request
├── data/
│   ├── input/          # place watchlist.csv here (git-ignored)
│   └── processed/      # loaded CSVs, renamed with a UTC timestamp (git-ignored)
├── sql/                # schema, run automatically when the database is created
├── src/
│   ├── extract.py      # CSV discovery, validation and reading
│   ├── load.py         # loading into PostgreSQL
│   ├── main.py         # entry point: runs the full pipeline
│   ├── matching.py     # matches each watchlist film with its TMDB id
│   └── tmdb_client.py  # TMDB API client (movie search)
├── tests/
├── .env.example        # template for your .env
├── .pre-commit-config.yaml
├── compose.yaml
├── pyproject.toml      # pytest and mypy configuration
├── requirements.txt
└── requirements-dev.txt
```

## Getting started

**Requirements:** Python 3.14 and Docker.

1. Clone the repository and create a virtual environment:

   ```bash
   git clone https://github.com/Berto797/proyecto-letterbox.git
   cd proyecto-letterbox
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-dev.txt
   pre-commit install
   ```

   `pre-commit install` sets up Git hooks that run Ruff and basic file checks before every commit.

2. Create your `.env` from the template and fill in the values:

   ```bash
   cp .env.example .env
   ```

   `POSTGRES_HOST=localhost` and `POSTGRES_PORT=5432` work with the provided `compose.yaml`.

   `TMDB_TOKEN` is your TMDB *API Read Access Token* (*Settings → API* on themoviedb.org). The pipeline does not use it yet.

3. Start the database:

   ```bash
   docker compose up -d
   ```

4. Export your watchlist from Letterboxd (*Settings → Data → Export your data*) and copy `watchlist.csv` into `data/input/`.

5. Run the pipeline:

   ```bash
   python src/main.py
   ```

   On success, the CSV is moved from `data/input/` to `data/processed/`. If any step fails, the error is printed to stderr, the program exits with code 1 and the CSV stays in `data/input/`.

   To copy the CSV instead of moving it (handy for repeated test runs), use `--keep-original`:

   ```bash
   python src/main.py --keep-original
   ```

> Each run loads the whole export again, as a new snapshot identified by its `source_file`. Duplicates across runs are expected in the raw layer.

## Tests

```bash
pytest
```

- **Unit tests** cover CSV discovery, validation and reading, file handling, and the row transformation before loading. They also cover the pipeline in `main.py`, with the database load replaced by a fake: the CSV is only moved after a successful load, and failures exit with code 1.
- **TMDB tests** never call the real API. The matching logic receives a fake search function, and the TMDB client runs against a fake HTTP session that records each request and returns prepared responses or errors.
- **Integration tests** run `load_raw` against a real, disposable PostgreSQL 17 started with [testcontainers](https://testcontainers.com/). The schema is created from the same `sql/` scripts used by Docker Compose, so tests never touch your development database.

> Docker must be running for the integration tests. Your `letterbox-db` container does not need to be up: testcontainers starts its own.

## Code quality

- **pre-commit** runs before every commit: Ruff (lint and format), trailing whitespace, final newlines, YAML syntax and large files.
- **mypy** checks types in strict mode across `src/` and `tests/`. Run it with `mypy`.
- **GitHub Actions** runs `ruff check`, `ruff format --check`, `mypy` and `pytest` on every pull request and on every push to `main`.

## Design decisions

- **Raw layer stores data as received.** All CSV columns are stored as `TEXT`, with no type conversion or cleaning. Rows with bad values are kept rather than rejected; cleaning belongs to later layers.
- **Unknown columns are not lost.** The required Letterboxd columns map to their own table columns; any extra column goes into an `extra_fields` JSONB column, so a change in the export format does not break the load.
- **All or nothing.** Every row is inserted in a single transaction: if one fails, nothing is saved.
- **The CSV is moved only after a successful load.** If loading fails, the file stays in `data/input/` and the run can simply be repeated.
- **Traceability.** Each row records its source file name (`watchlist_<timestamp>.csv`) and load time, so every load can be traced back to its file.
- **UTC timestamps** everywhere.
- **Configuration through environment variables.** No credentials or connection details in the code.
- **Conservative TMDB matching.** A film is matched only when its title equals the TMDB `title` or `original_title` after removing accents and case. When the film has a year, the search is filtered by it; if nothing matches, it is repeated without the year and only results within ±1 year are kept. One candidate is `matched`; several are `ambiguous` (the one with most votes is kept, for review); none is `not_found`.

## Roadmap

- [x] CSV extraction and validation
- [x] Loading into PostgreSQL (raw layer)
- [x] Unit tests
- [x] Integration tests for the load with testcontainers
- [x] `main.py` orchestrating extract → load → move to processed
- [x] CI with GitHub Actions and pre-commit hooks
- [ ] Enrichment with TMDB data
  - [x] TMDB client and title-matching logic
  - [ ] Store the matches in PostgreSQL
  - [ ] Download movie details from TMDB

## Disclaimer

This is a personal, non-commercial project.

- This product uses the TMDB API but is not endorsed or certified by [TMDB](https://www.themoviedb.org/).
- Not affiliated with Letterboxd. It only processes the CSV that each user exports from their own account.
