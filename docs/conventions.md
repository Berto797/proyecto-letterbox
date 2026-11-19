# Coding conventions

This guide collects the conventions followed in this project. Anything that a tool already checks (formatting, line length, import order, docstring format, types) is enforced by Ruff, mypy, pre-commit and CI, and is only mentioned here. The rest of the guide covers what tools cannot check.

## 1. Language

| English | Spanish |
| --- | --- |
| Identifiers: variables, functions, classes, constants, tables and columns | Docstrings and comments |
| Documentation: the `README.md` in the root and the files in `docs/` | Messages for the user, including error messages |
| | Commit messages, pull requests and issues |

## 2. What the tools check

- **Ruff** formats the code and checks the lint rules: line length of 88 (`E501`), import order (`I`) and docstrings in Google style (`D`). In `tests/`, modules, test functions and test doubles do not need docstrings.
- **mypy** checks types in strict mode across `src/` and `tests/`: every parameter and return value is annotated.
- **pre-commit** runs Ruff and basic file checks before every commit.
- **GitHub Actions** runs Ruff, mypy and pytest on every pull request and on every push to `main`.

If a rule can be automated, it is added to the tools instead of to this guide.

## 3. Module layout

Every module in `src/` follows the same order:

1. Module docstring: one line describing what the module contains.
2. Imports.
3. Constants, including SQL queries.
4. Classes (dataclasses, enums, clients).
5. Internal functions (`_name`).
6. Public functions.

Each helper is defined **before** the functions that call it, so a module can be read from top to bottom without meeting a name that has not been defined yet. Independent helpers go in the order in which they are used. `matching.py` and `review.py` are good examples.

## 4. Naming

- **Internal vs public.** A function is public when it is a complete operation that makes sense on its own (`read_manual_matches`, `get_films_to_review`, `save_match`), even if `main.py` does not call it. Steps that only make sense inside another function are internal (`_parse_manual_row`, `_validate_known_uris`).
- **Constants** are in upper case. SQL constants are named after the action and its object: `GET_PENDING_FILMS`, `GET_KNOWN_URIS`, `UPSERT_TMDB_MATCHES`.
- **`_validate_*` functions** return `None` or raise an error, so they read as a check: `_validate_manual_headers`, `_validate_known_uris`.
- **Names say what something is**, not its type: `manual_match` rather than `match` (it could be confused with a `MatchResult`), `applied_count` rather than `result`, `known_uris` rather than `result_set`.

## 5. Types and classes

- **Parameters use abstract types and return values use concrete ones:** `Sequence` and `Mapping` for parameters, `list` and `dict` for return values. A function then accepts any sequence, and its callers know exactly what they get.

  ```python
  def _write_review_csv(path: Path, films: Sequence[FilmToReview]) -> None: ...
  def read_manual_matches(path: Path) -> list[ManualMatch]: ...
  ```

- **Use a class when it makes the code clearer, never just for show:**
  - `@dataclass(frozen=True)` for records with named fields (`ManualMatch`, `FilmToReview`, `MatchResult`).
  - `StrEnum` for a closed set of values (`MatchStatus`).
  - A regular class when calls share state (`TMDBClient`, which keeps an authenticated HTTP session).
  - Plain functions and dicts for pure transformations and raw-layer rows.
- **Types must be honest.** A dataclass filled from PostgreSQL with `class_row` receives the values as they come from the database, without conversion: a `TEXT` column is a `str`, even if it holds a `MatchStatus` value, and a nullable column is `X | None`.

## 6. Docstrings

- **Internal functions, classes and modules:** one line, written in Spanish, ending with a period.
- **Public functions:** Google style, with a summary line, a paragraph explaining the behaviour and the `Args`, `Returns` and `Raises` sections.
- **Explain what the signature does not show:** for example, who is responsible for the commit (`save_match` does not commit), whether a function opens its own connection, or why a file is always rewritten.
- **Fixed terms:**
  - *el* `letterboxd_uri` (masculine).
  - *encabezados*, not *headers*.
  - The match statuses are written as in the database: `matched`, `ambiguous`, `not_found`, `manual`.

## 7. Errors

- Invalid data raises `ValueError` with a message that tells the user what to fix: which file, which line and which value.

  ```python
  raise ValueError(
      f"El tmdb_id de la línea {line_num} de {path.name} "
      f"no es un número entero: {tmdb_id_text!r}"
  )
  ```

- When an error is turned into another one, the original is kept with `raise ... from e`.
- Never `except Exception`: catch only the errors that are expected.
- Only the entry point (`main.py`) catches errors. It prints them to stderr and exits with code 1; the other modules let them propagate.

## 8. Database

- **Whoever decides the transaction opens the connection.**
  - *Pieces* that run a single query receive the connection as a parameter and do not commit: `get_pending_films(conn)`, `save_match(conn, ...)`, `get_films_to_review(conn)`. They can be combined in one transaction and tested inside a single `with` block.
  - *Processes* open their own connection and decide when to commit: `match_pending_films` commits after every film, `apply_manual_matches` commits once (all or nothing).
- **Queries are always parameterized** with named placeholders and a dict, never built with f-strings:

  ```python
  conn.execute(GET_KNOWN_URIS, {"uris": uris})
  ```

  A Python `list` is sent as a PostgreSQL array (`= ANY(%(uris)s)`); a `set` is not accepted.
- **SQL lives in module constants**, not inside functions. Queries with several steps use CTEs (`WITH ... AS (...)`), one step per CTE.
- **The schema lives in `sql/`** and is created by Docker Compose and by the integration tests from the same files.

## 9. Files

- CSV files are opened with `newline=""` and `encoding="utf-8-sig"`. When reading, it accepts files with or without a BOM. When writing, it adds a BOM so Excel shows accents correctly.
- Functions receive paths as parameters. The real paths are defined as constants in the module that decides them (`INPUT_DIR` in `extract.py`, `MANUAL_MATCHES_PATH` and `REVIEW_PATH` in `main.py`).

## 10. Tests

- **Names:** `test_<function>_<case>`, for example `test_apply_manual_matches_unknown_uri`. The same case has the same name in every function (`file_not_exists`, `empty`).
- **Parameters:** fixtures first, then the `parametrize` arguments.
- **Structure:** arrange, act and assert, separated by blank lines.
  - If the function receives the connection, everything happens inside one `with open_connection() as conn:` block.
  - If the function opens its own connection, use three blocks: insert the data (the `with` block commits on exit), call the function outside any `with`, and open a new connection to check the result.
- **Parameterized cases** use `pytest.param(..., id="...")` with ids that follow `<what>_<problem>`: `tmdb_id_negative`, `file_not_utf8`, `letterboxd_uri_duplicate`.
- **Test data** goes in module constants (`VALID_MANUAL_CSV`, `EXPECTED_REVIEW_CSV`). Data is chosen and inserted so that the test fails if the code is wrong: for example, rows are inserted in a different order from the expected one to check an `ORDER BY`.
- **What to test:** the public interface by default. Internal functions are tested directly only when the public one depends on something external (a fixed folder, the database, the API) or when they hold logic with many cases (`_normalize_title`, `_decide`).
- **No docstrings** in test functions: the name says what they check. Fixtures and helpers do have a one-line docstring, and an `autouse` fixture explains in it why it applies to every test.
- **Shared database helpers** live in `tests/db_helpers.py`. Tests never import from other test modules.
- **Tests never call the real TMDB API and never read `.env`.** Integration tests use a disposable PostgreSQL started by testcontainers.

## 11. Git and GitHub

- **Branches** start from an up-to-date `main`: `feature/<name>` for new functionality and `chore/<name>` for maintenance.
- **Commit messages** are in Spanish and start with a verb in the infinitive: *Añadir…*, *Mover…*, *Activar…*.
- **One logical change per commit**, with its tests in the same commit. Refactors go in their own commit, before the change that needs them, and every commit passes the tests.
- **Issues** describe pending work and use the `cleanup` label (no change in behaviour) or `enhancement` (new or better behaviour). A pull request that solves an issue says `Closes #N` in its description.
- **Pull requests** are written in Spanish and describe what is included, how it is tested and the next steps.
