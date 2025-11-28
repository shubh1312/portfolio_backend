-- =====================================================
-- Users
-- =====================================================

CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    email           TEXT UNIQUE NOT NULL,
    name            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =====================================================
-- Portfolios (each belongs to a user)
-- Only active portfolios are synced by cron.
-- =====================================================

CREATE TABLE portfolios (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,              -- "Long Term", "US Stocks"
    description     TEXT,
    is_default      BOOLEAN NOT NULL DEFAULT FALSE,
    active          BOOLEAN NOT NULL DEFAULT TRUE,  -- only active ones are synced
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_portfolios_user_id ON portfolios(user_id);

-- Optional: enforce at most one default portfolio per user
-- CREATE UNIQUE INDEX uniq_default_portfolio_per_user
--   ON portfolios(user_id)
--   WHERE is_default = TRUE;

-- =====================================================
-- Broker Types (Zerodha, INDmoney, Vested, etc.)
-- =====================================================

CREATE TABLE broker_types (
    id              BIGSERIAL PRIMARY KEY,
    code            TEXT UNIQUE NOT NULL,       -- 'ZERODHA', 'INDMONEY', 'VESTED'
    display_name    TEXT NOT NULL              -- 'Zerodha', 'INDmoney', ...
);

-- Example seed:
-- INSERT INTO broker_types (code, display_name) VALUES
-- ('ZERODHA', 'Zerodha'),
-- ('INDMONEY', 'INDmoney'),
-- ('VESTED', 'Vested');

-- =====================================================
-- Broker Accounts
-- One real account/login at a broker, attached to ONE portfolio.
-- (User is derived via portfolio -> user)
-- =====================================================

CREATE TABLE broker_accounts (
    id                  BIGSERIAL PRIMARY KEY,
    portfolio_id        BIGINT NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    broker_type_id      BIGINT NOT NULL REFERENCES broker_types(id) ON DELETE RESTRICT,

    external_account_id TEXT NOT NULL,     -- client id / account id at broker
    display_name        TEXT,              -- "Zerodha main", "US account #1", etc.
    status              TEXT NOT NULL DEFAULT 'active',  -- 'active', 'disabled'
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_broker_accounts_portfolio_id ON broker_accounts(portfolio_id);
CREATE INDEX idx_broker_accounts_broker_type_id ON broker_accounts(broker_type_id);

-- Same broker login can't appear twice under same broker_type
CREATE UNIQUE INDEX uniq_broker_account_per_broker_type
    ON broker_accounts (broker_type_id, external_account_id);

-- =====================================================
-- Broker Account Credentials
-- One row per broker account, with broker-specific JSONB credentials.
-- =====================================================

CREATE TABLE broker_account_credentials (
    id                BIGSERIAL PRIMARY KEY,
    broker_account_id BIGINT NOT NULL UNIQUE
                      REFERENCES broker_accounts(id) ON DELETE CASCADE,

    credentials       JSONB NOT NULL,      -- flexible broker-wise JSON
    encrypted         BOOLEAN NOT NULL DEFAULT FALSE,

    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_credentials_gin ON broker_account_credentials
    USING GIN (credentials);

-- =====================================================
-- Holdings
-- Snapshot of positions per broker account.
-- Supports stocks, ETFs, MFs, gold, EPF, etc.
-- =====================================================

CREATE TABLE holdings (
    id                  BIGSERIAL PRIMARY KEY,
    broker_account_id   BIGINT NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,

    asset_type          TEXT NOT NULL,           -- 'stock', 'etf', 'mf', 'gold', 'epf', ...
    symbol              TEXT NOT NULL,           -- 'TCS', 'NIFTYBEES', 'AXISBLUECHIP'
    isin                TEXT,                    -- optional but useful

    quantity            NUMERIC(20, 6) NOT NULL,
    avg_price           NUMERIC(20, 6) NOT NULL, -- per-unit cost
    currency            TEXT NOT NULL DEFAULT 'INR',

    cost_value          NUMERIC(20, 6),          -- quantity * avg_price (optional cache)
    market_value        NUMERIC(20, 6),          -- last known valuation (optional)

    as_of               TIMESTAMPTZ NOT NULL,    -- when this snapshot is valid at broker
    source_snapshot_id  TEXT,                    -- broker's snapshot/version id (optional)

    meta                JSONB,                   -- raw broker data / extra fields
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_holdings_broker_account_id ON holdings(broker_account_id);
CREATE INDEX idx_holdings_symbol ON holdings(symbol);
CREATE INDEX idx_holdings_as_of ON holdings(as_of);

-- Optional: if you want at most one snapshot per (account, symbol, as_of)
-- CREATE UNIQUE INDEX uniq_holding_snapshot
--   ON holdings (broker_account_id, symbol, as_of);

-- =====================================================
-- Transactions
-- Individual trades / cashflows per broker account.
-- =====================================================

CREATE TABLE transactions (
    id                  BIGSERIAL PRIMARY KEY,
    broker_account_id   BIGINT NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,

    asset_type          TEXT NOT NULL,          -- 'stock', 'mf', 'gold', etc.
    symbol              TEXT NOT NULL,
    quantity            NUMERIC(20, 6) NOT NULL,
    price               NUMERIC(20, 6) NOT NULL,  -- per-unit for BUY/SELL
    currency            TEXT NOT NULL DEFAULT 'INR',

    trade_type          TEXT NOT NULL,          -- 'BUY', 'SELL', 'DIVIDEND', 'FEE', etc.
    trade_time          TIMESTAMPTZ NOT NULL,   -- when trade executed at broker

    meta                JSONB,                  -- any broker-specific details
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_transactions_broker_account_id ON transactions(broker_account_id);
CREATE INDEX idx_transactions_symbol ON transactions(symbol);
CREATE INDEX idx_transactions_trade_time ON transactions(trade_time);
