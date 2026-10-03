CREATE TABLE IF NOT EXISTS raw_watchlist (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    watchlisted_at      TEXT,
    film_name           TEXT,
    film_year           TEXT,
    letterboxd_uri      TEXT,
    extra_fields        JSONB NOT NULL DEFAULT '{}',
    source_file         TEXT NOT NULL,
    loaded_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
