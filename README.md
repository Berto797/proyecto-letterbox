# proyecto-letterbox

A data pipeline that loads a [Letterboxd](https://letterboxd.com/) watchlist export into PostgreSQL, as the first step towards enriching it with data from [TMDB](https://www.themoviedb.org/).

> **Status:** work in progress. Extraction and loading into the raw layer are working; TMDB enrichment is not implemented yet.

## How it works

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
- pytest, testcontainers
- Ruff (linting and formatting)

## Project structure

```
├── data/
│   ├── input/          # place watchlist.csv here (git-ignored)
│   └── processed/      # loaded CSVs, renamed with a UTC timestamp (git-ignored)
├── sql/                # schema, run automatically when the database is created
├── src/
│   ├── extract.py      # CSV discovery, validation and reading
│   └── load.py         # loading into PostgreSQL
├── tests/
├── compose.yaml
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
   ```

2. Create your `.env` from the template and fill in the values:

   ```bash
   cp .env.example .env
   ```

   `POSTGRES_HOST=localhost` and `POSTGRES_PORT=5432` work with the provided `compose.yaml`.

3. Start the database:

   ```bash
   docker compose up -d
   ```

4. Export your watchlist from Letterboxd (*Settings → Data → Export your data*) and copy `watchlist.csv` into `data/input/`.

5. Run the load:

   ```bash
   python src/load.py
   ```

> For now `load.py` loads the data but does not move the CSV to `data/processed/`. The full pipeline will be orchestrated by a `main.py` (see [Roadmap](#roadmap)).

## Tests

```bash
pytest
```

## Design decisions

- **Raw layer stores data as received.** All CSV columns are stored as `TEXT`, with no type conversion or cleaning. Rows with bad values are kept rather than rejected; cleaning belongs to later layers.
- **Unknown columns are not lost.** The required Letterboxd columns map to their own table columns; any extra column goes into an `extra_fields` JSONB column, so a change in the export format does not break the load.
- **All or nothing.** Every row is inserted in a single transaction: if one fails, nothing is saved.
- **The CSV is moved only after a successful load.** If loading fails, the file stays in `data/input/` and the run can simply be repeated.
- **Traceability.** Each row records its source file name (`watchlist_<timestamp>.csv`) and load time, so every load can be traced back to its file.
- **UTC timestamps** everywhere.
- **Configuration through environment variables.** No credentials or connection details in the code.

## Roadmap

- [x] CSV extraction and validation
- [x] Loading into PostgreSQL (raw layer)
- [x] Unit tests
- [ ] Integration tests for the load with testcontainers
- [ ] `main.py` orchestrating extract → load → move to processed
- [ ] Enrichment with TMDB data
