-- Provisional v0 schema. Phase 1 (ingestion) and Phase 2 (dbt marts) will refine it.
-- Idempotent so it can be applied on container init and again in CI.

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS core;

-- Every API response is kept verbatim so parsing bugs can be fixed and replayed later.
CREATE TABLE IF NOT EXISTS raw.api_payload (
    id          BIGSERIAL PRIMARY KEY,
    venue       TEXT        NOT NULL,
    endpoint    TEXT        NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    http_status INTEGER     NOT NULL,
    payload     JSONB       NOT NULL
);
CREATE INDEX IF NOT EXISTS api_payload_venue_fetched_idx
    ON raw.api_payload (venue, fetched_at DESC);

-- One row per tradable contract (a single outcome of a possibly multi-outcome event).
CREATE TABLE IF NOT EXISTS core.market (
    market_id       TEXT PRIMARY KEY,              -- '<venue>:<native_id>'
    venue           TEXT        NOT NULL,
    native_id       TEXT        NOT NULL,
    event_key       TEXT        NOT NULL,          -- venue-agnostic event, e.g. 'fomc-2026-10'
    title           TEXT        NOT NULL,
    outcome_label   TEXT        NOT NULL,
    kind            TEXT        NOT NULL CHECK (kind IN ('bucket', 'threshold')),
    bucket_bps      INTEGER,                       -- bucket markets: change in the Fed's upper bound
    strike_pct      NUMERIC,                       -- threshold markets: "above X%"
    resolution_rule TEXT,                          -- stored because rules differ across venues
    close_time      TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    resolved_yes    BOOLEAN,
    UNIQUE (venue, native_id)
);
CREATE INDEX IF NOT EXISTS market_event_key_idx ON core.market (event_key);

CREATE TABLE IF NOT EXISTS core.market_snapshot (
    market_id  TEXT        NOT NULL REFERENCES core.market (market_id),
    ts         TIMESTAMPTZ NOT NULL,
    best_bid   NUMERIC(6, 5) CHECK (best_bid BETWEEN 0 AND 1),
    best_ask   NUMERIC(6, 5) CHECK (best_ask BETWEEN 0 AND 1),
    bid_size   NUMERIC,
    ask_size   NUMERIC,
    last_price NUMERIC(6, 5) CHECK (last_price BETWEEN 0 AND 1),
    volume_24h NUMERIC,
    PRIMARY KEY (market_id, ts),
    CHECK (best_bid IS NULL OR best_ask IS NULL OR best_bid <= best_ask)
);

-- Macro series stored with vintage dates (ALFRED realtime_start/end) so that any
-- backtest can ask "what did we know on date D?" and avoid look-ahead leakage.
CREATE TABLE IF NOT EXISTS core.macro_observation (
    series_id      TEXT    NOT NULL,
    obs_date       DATE    NOT NULL,
    realtime_start DATE    NOT NULL,
    realtime_end   DATE    NOT NULL,
    value          NUMERIC,
    PRIMARY KEY (series_id, obs_date, realtime_start)
);

-- ---- Crypto touch markets and the live pricer (added with the crypto vertical) -----------------
-- Idempotent migrations so an existing database picks these up without being recreated.
ALTER TABLE core.market ADD COLUMN IF NOT EXISTS barrier       NUMERIC;
ALTER TABLE core.market ADD COLUMN IF NOT EXISTS direction     TEXT CHECK (direction IN ('up', 'down'));
ALTER TABLE core.market ADD COLUMN IF NOT EXISTS window_start  TIMESTAMPTZ;
ALTER TABLE core.market ADD COLUMN IF NOT EXISTS fee_rate      NUMERIC;
ALTER TABLE core.market ADD COLUMN IF NOT EXISTS fee_exponent  NUMERIC;
ALTER TABLE core.market DROP CONSTRAINT IF EXISTS market_kind_check;
ALTER TABLE core.market ADD CONSTRAINT market_kind_check
    CHECK (kind IN ('bucket', 'threshold', 'touch'));

-- Hourly spot candles from the exchange used to feed the volatility model.
CREATE TABLE IF NOT EXISTS core.spot_bar (
    asset  TEXT        NOT NULL,
    ts     TIMESTAMPTZ NOT NULL,          -- start of the candle
    open   NUMERIC     NOT NULL,
    high   NUMERIC     NOT NULL,
    low    NUMERIC     NOT NULL,
    close  NUMERIC     NOT NULL,
    volume NUMERIC,
    PRIMARY KEY (asset, ts)
);

-- One row per market per pricing cycle: what the model thinks, what the market says, the edge.
CREATE TABLE IF NOT EXISTS core.fair_value (
    market_id       TEXT        NOT NULL REFERENCES core.market (market_id),
    ts              TIMESTAMPTZ NOT NULL,
    model_id        TEXT        NOT NULL,   -- includes a hash of the model artifact and config
    p               DOUBLE PRECISION NOT NULL CHECK (p BETWEEN 0 AND 1),
    p_low           DOUBLE PRECISION CHECK (p_low BETWEEN 0 AND 1),
    p_high          DOUBLE PRECISION CHECK (p_high BETWEEN 0 AND 1),
    mid             DOUBLE PRECISION,
    bid             DOUBLE PRECISION,
    ask             DOUBLE PRECISION,
    edge_buy        DOUBLE PRECISION,       -- p minus all-in cost of buying Yes (fee included)
    edge_sell       DOUBLE PRECISION,       -- all-in proceeds of selling Yes minus p
    implied_vol     DOUBLE PRECISION,       -- volatility implied by the market mid (NULL if impossible)
    spot            DOUBLE PRECISION,
    sigma_median    DOUBLE PRECISION,       -- model's median annualised volatility for this horizon
    already_touched BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (market_id, ts, model_id)
);
CREATE INDEX IF NOT EXISTS fair_value_ts_idx ON core.fair_value (ts DESC);

-- ---- Backtest results, loaded from outputs/*.parquet for the Grafana research dashboard -------
CREATE TABLE IF NOT EXISTS core.backtest_score (
    asset               TEXT    NOT NULL,
    year                INTEGER NOT NULL,      -- 0 means "all years combined"
    model               TEXT    NOT NULL,
    n                   BIGINT  NOT NULL,
    log_loss            DOUBLE PRECISION NOT NULL,
    brier               DOUBLE PRECISION NOT NULL,
    brier_skill_vs_naive DOUBLE PRECISION NOT NULL,
    calibration_slope   DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (asset, year, model)
);

CREATE TABLE IF NOT EXISTS core.backtest_diff (
    asset          TEXT NOT NULL,
    model          TEXT NOT NULL,
    vs             TEXT NOT NULL,
    log_loss_diff  DOUBLE PRECISION NOT NULL,
    ci_low         DOUBLE PRECISION NOT NULL,
    ci_high        DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (asset, model, vs)
);
