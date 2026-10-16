CREATE TABLE IF NOT EXISTS tmdb_matches (
    letterboxd_uri      TEXT PRIMARY KEY,
    tmdb_id             BIGINT,
    match_status        TEXT NOT NULL CHECK (match_status IN ('matched', 'ambiguous', 'not_found', 'manual')),
    matched_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (tmdb_id IS NULL AND match_status = 'not_found')
        OR (tmdb_id IS NOT NULL AND match_status != 'not_found')
    )
);
