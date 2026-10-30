# proyecto-letterbox

A data pipeline that loads a [Letterboxd](https://letterboxd.com/) watchlist export into PostgreSQL and matches each film with its [TMDB](https://www.themoviedb.org/) id, as the first step towards enriching it with data from TMDB.

> **Status:** work in progress. Extraction, loading into the raw layer and matching with TMDB are working: each film is searched on TMDB and the result is stored in PostgreSQL. Next steps are reviewing ambiguous and not-found matches by hand and downloading the movie details.

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
        │
        ▼
    match   ──  searches TMDB for every film not yet in tmdb_matches
                and saves the result (one commit per film)
```

For each film, `tmdb_matches` stores its TMDB id (empty when `not_found`), the match status and when it was saved. The last step reads the films from the database, not from the CSV, so it can also be run on its own with `--match-only`.

## Tech stack

- Python 3.14
- PostgreSQL 17 (Docker Compose)
- psycopg 3
- requests (TMDB API)
- python-dotenv (loads the `.env` file)
- pytest, testcontainers (integration tests)
- Ruff (linting and formatting)
- mypy (static type checking, strict mode)
- pre-commit (Git hooks)
- GitHub Actions (CI)

## Project structure

```
├── .github/workflows/  # CI: Ruff, mypy and pytest on every pull request and push to main
├── data/
│   ├── input/          # place watchlist.csv here (git-ignored)
│   └── processed/      # loaded CSVs, renamed with a UTC timestamp (git-ignored)
├── sql/                # schema, run automatically when the database is created
├── src/
│   ├── db.py           # PostgreSQL connection from the POSTGRES_* variables
│   ├── extract.py      # CSV discovery, validation and reading
│   ├── load.py         # loading into PostgreSQL
│   ├── main.py         # entry point: runs the full pipeline
│   ├── matching.py     # matches each watchlist film with its TMDB id
│   ├── tmdb_client.py  # TMDB API client (movie search)
│   └── tmdb_matches.py # finds pending films, matches them and saves the results
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

   `TMDB_TOKEN` is your TMDB *API Read Access Token* (*Settings → API* on themoviedb.org). The pipeline uses it to search each film on TMDB.

3. Start the database:

   ```bash
   docker compose up -d
   ```

4. Export your watchlist from Letterboxd (*Settings → Data → Export your data*) and copy `watchlist.csv` into `data/input/`.

5. Run the pipeline:

   ```bash
   python src/main.py
   ```

   After a successful load, the CSV is moved from `data/input/` to `data/processed/`. Then every film that is not yet in `tmdb_matches` is searched on TMDB, and a summary by status is printed (for example, `Se han emparejado 192 películas: matched 174, ambiguous 16, not_found 2`). If any step fails, the error is printed to stderr and the program exits with code 1. If the load fails, the CSV stays in `data/input/`; if the matching fails, the films matched so far are kept.

   To copy the CSV instead of moving it (handy for repeated test runs), use `--keep-original` (`-k`):

   ```bash
   python src/main.py --keep-original
   ```

   To only match the pending films, without loading any CSV (for example, to resume after a TMDB error), use `--match-only` (`-m`):

   ```bash
   python src/main.py --match-only
   ```

> Each run loads the whole export again, as a new snapshot identified by its `source_file`. Duplicates across runs are expected in the raw layer. Films that already have a row in `tmdb_matches` are not searched again.

## Tests

```bash
pytest
```

- **Unit tests** cover CSV discovery, validation and reading, file handling, and the row transformation before loading. They also cover the pipeline in `main.py`, with the database load and the TMDB matching replaced by fakes: the CSV is only moved after a successful load, `--match-only` skips the load, and failures (including a missing `TMDB_TOKEN` or a TMDB error) exit with code 1.
- **TMDB tests** never call the real API. The matching logic receives a fake search function, and the TMDB client runs against a fake HTTP session that records each request and returns prepared responses or errors.
- **Integration tests** run `load_raw` and the `tmdb_matches` functions (finding pending films, saving matches and the full matching run, with a fake TMDB search) against a real, disposable PostgreSQL 17 started with [testcontainers](https://testcontainers.com/). The schema is created from the same `sql/` scripts used by Docker Compose, so tests never touch your development database.
- Tests never read your `.env`: it is only loaded when `main.py` is run from the command line.

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
- **Configuration through environment variables.** No credentials or connection details in the code. The `.env` file is loaded only at the entry point (`main.py`); the other modules read the variables but never load the file.
- **Conservative TMDB matching.** A film is matched only when its title equals the TMDB `title` or `original_title` after removing accents and case. When the film has a year, the search is filtered by it; if nothing matches, it is repeated without the year and only results within ±1 year are kept. One candidate is `matched`; several are `ambiguous` (the one with most votes is kept, for review); none is `not_found`.
- **Pending films are those without a match.** The matching step takes the latest version of each film (by `letterboxd_uri`) from `raw_watchlist` and skips the ones that already have a row in `tmdb_matches`, so repeated loads do not cause repeated searches.
- **Resumable matching.** Each match is committed as soon as it is saved. If a TMDB request fails, the run stops instead of skipping the film, the matches already saved are kept, and the next run continues with the films that are still pending.

## Roadmap

- [x] CSV extraction and validation
- [x] Loading into PostgreSQL (raw layer)
- [x] Unit tests
- [x] Integration tests for the load with testcontainers
- [x] `main.py` orchestrating extract → load → move to processed
- [x] CI with GitHub Actions and pre-commit hooks
- [ ] Enrichment with TMDB data
  - [x] TMDB client and title-matching logic
  - [x] Store the matches in PostgreSQL
  - [ ] Review ambiguous and not-found matches by hand
  - [ ] Download movie details from TMDB

## Disclaimer

This is a personal, non-commercial project.

- This product uses the TMDB API but is not endorsed or certified by [TMDB](https://www.themoviedb.org/).
- Not affiliated with Letterboxd. It only processes the CSV that each user exports from their own account.
