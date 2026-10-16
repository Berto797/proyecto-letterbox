CREATE TABLE IF NOT EXISTS raw_tmdb_movies (
    tmdb_id             BIGINT PRIMARY KEY,
    response            JSONB NOT NULL,
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
