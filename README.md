# proyecto-letterbox

A data pipeline that loads a [Letterboxd](https://letterboxd.com/) watchlist export into PostgreSQL and matches each film with its [TMDB](https://www.themoviedb.org/) id, as the first step towards enriching it with data from TMDB.

> **Status:** work in progress. Extraction, loading into the raw layer and matching with TMDB are working: each film is searched on TMDB, the result is stored in PostgreSQL, and ambiguous or not-found matches can be reviewed and fixed by hand. The next step is downloading the movie details.

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
   manual   ──  saves the matches written by hand in data/manual_matches.csv
                (optional file, single transaction)
        │
        ▼
    match   ──  searches TMDB for every film not yet in tmdb_matches
                and saves the result (one commit per film)
        │
        ▼
   review   ──  writes the ambiguous and not_found films
                to data/review/pending_matches.csv
```

For each film, `tmdb_matches` stores its TMDB id (empty when `not_found`), the match status (`matched`, `ambiguous`, `not_found` or `manual`) and when it was saved. The steps after the load read the films from the database, not from the CSV, so they can also be run on their own with `--match-only`.

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
│   ├── processed/      # loaded CSVs, renamed with a UTC timestamp (git-ignored)
│   ├── review/         # pending_matches.csv, regenerated on every run (git-ignored)
│   ├── manual_matches.csv          # your manual matches (optional, git-ignored)
│   └── manual_matches.example.csv  # template for manual_matches.csv
├── docs/
│   └── conventions.md  # coding conventions
├── sql/                # schema, run automatically when the database is created
├── src/
│   ├── db.py           # PostgreSQL connection from the POSTGRES_* variables
│   ├── extract.py      # CSV discovery, validation and reading
│   ├── load.py         # loading into PostgreSQL
│   ├── main.py         # entry point: runs the full pipeline
│   ├── matching.py     # matches each watchlist film with its TMDB id
│   ├── review.py       # manual matches and the review file
│   ├── tmdb_client.py  # TMDB API client (movie search)
│   └── tmdb_matches.py # finds pending films, matches them and saves the results
├── tests/
├── .env.example        # template for your .env
├── CLAUDE.md           # instructions for Claude Code
├── .pre-commit-config.yaml
├── compose.yaml
├── pyproject.toml      # pytest, mypy and Ruff configuration
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

   After a successful load, the CSV is moved from `data/input/` to `data/processed/`. Then the manual matches are applied (see step 6), every film that is not yet in `tmdb_matches` is searched on TMDB, and a summary by status is printed (for example, `Se han emparejado 192 películas: matched 174, ambiguous 16, not_found 2`). Finally, the films to review are written to `data/review/pending_matches.csv` (for example, `Hay 18 películas por revisar en data/review/pending_matches.csv`). If any step fails, the error is printed to stderr and the program exits with code 1. If the load fails, the CSV stays in `data/input/`; if the matching fails, the films matched so far are kept.

   To copy the CSV instead of moving it (handy for repeated test runs), use `--keep-original` (`-k`):

   ```bash
   python src/main.py --keep-original
   ```

   To skip the load and run only the other steps (for example, to resume after a TMDB error or to apply new manual matches), use `--match-only` (`-m`):

   ```bash
   python src/main.py --match-only
   ```

6. Review the matches. Open `data/review/pending_matches.csv` (it opens correctly in Excel). It lists every `ambiguous` and `not_found` film with a link to check it on TMDB: for `ambiguous` films, the link opens the proposed candidate (`tmdb_id`); for `not_found` films, it opens a TMDB search for the title.

   To fix a film, copy its row into `data/manual_matches.csv` (start from the template the first time) and set the right `tmdb_id`. The first four columns are the same in both files, so whole rows can be copied; the extra columns are ignored.

   ```bash
   cp data/manual_matches.example.csv data/manual_matches.csv
   ```

   ```
   letterboxd_uri,tmdb_id,film_name,film_year
   https://boxd.it/2aLE,251,Ghost,1990
   ```

   Then run the pipeline again (`python src/main.py --match-only` is enough). The films in the file are saved as `manual`, replacing their previous match, and disappear from the review file. Films with no equivalent on TMDB (for example, TV series) can be left out: they stay as `not_found`.

> Each run loads the whole export again, as a new snapshot identified by its `source_file`. Duplicates across runs are expected in the raw layer. Films that already have a row in `tmdb_matches` are not searched again.

## Tests

```bash
pytest
```

- **Unit tests** cover CSV discovery, validation and reading, file handling, and the row transformation before loading. They also cover reading and validating `manual_matches.csv` and writing the review file (columns, TMDB links, empty file, BOM), and check that a row copied from the review file can be read as a manual match. The pipeline in `main.py` is tested with the database and TMDB steps replaced by fakes: the CSV is only moved after a successful load, `--match-only` skips the load, the steps run in order (manual → match → review), and failures (including a missing `TMDB_TOKEN`, a TMDB error, an invalid manual file or a review file that cannot be written) exit with code 1.
- **TMDB tests** never call the real API. The matching logic receives a fake search function, and the TMDB client runs against a fake HTTP session that records each request and returns prepared responses or errors.
- **Integration tests** run `load_raw`, the `tmdb_matches` functions (finding pending films, saving matches and the full matching run, with a fake TMDB search) and the `review` functions (applying manual matches and finding and writing the films to review) against a real, disposable PostgreSQL 17 started with [testcontainers](https://testcontainers.com/). The schema is created from the same `sql/` scripts used by Docker Compose, so tests never touch your development database.
- Tests never read your `.env`: it is only loaded when `main.py` is run from the command line.

> Docker must be running for the integration tests. Your `letterbox-db` container does not need to be up: testcontainers starts its own.

## Code quality

- **pre-commit** runs before every commit: Ruff (lint and format), trailing whitespace, final newlines, YAML syntax and large files.
- **mypy** checks types in strict mode across `src/` and `tests/`. Run it with `mypy`.
- **GitHub Actions** runs `ruff check`, `ruff format --check`, `mypy` and `pytest` on every pull request and on every push to `main`.
- **Coding conventions** that tools cannot check (module layout, naming, errors, database access, tests, commits) are described in [`docs/conventions.md`](docs/conventions.md). [`CLAUDE.md`](CLAUDE.md) points Claude Code to the same guide.

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
- **Manual matches take precedence.** Films in `data/manual_matches.csv` are saved with the `manual` status, replacing any automatic match, and are never searched on TMDB. They are applied before the automatic matching, so a film added to the file is not searched first. The file is applied on every run.
- **The manual file is applied all or nothing.** It is validated before anything is saved (required columns, a positive integer `tmdb_id`, no repeated films) and every film must be in the watchlist; if any check fails, no row is saved and the error names the line or the films to fix.
- **The review file is regenerated on every run,** even when there is nothing to review (then it only has the header), so an old file with films already fixed is never left behind.
- **The review file is easy to act on.** Its first columns follow the order of `manual_matches.csv`, so rows can be copied as they are, and each film has a link to TMDB instead of the full list of candidates. It is written with a UTF-8 BOM so Excel shows accents correctly.
- **Films that are not on TMDB stay `not_found`.** There is no special status for them: leaving them out of the manual file is enough.

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
  - [x] Review ambiguous and not-found matches by hand
  - [ ] Download movie details from TMDB

## Disclaimer

This is a personal, non-commercial project.

- This product uses the TMDB API but is not endorsed or certified by [TMDB](https://www.themoviedb.org/).
- Not affiliated with Letterboxd. It only processes the CSV that each user exports from their own account.
