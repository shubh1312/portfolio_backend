# Database Schema ER Diagram
mermaid

erDiagram
    USERS ||--o{ PORTFOLIOS : owns
    PORTFOLIOS ||--o{ BROKER_ACCOUNTS : owns
    BROKER_TYPES ||--o{ BROKER_ACCOUNTS : categorizes
    BROKER_ACCOUNTS ||--|| BROKER_ACCOUNT_CREDENTIALS : has
    BROKER_ACCOUNTS ||--o{ HOLDINGS : contains
    BROKER_ACCOUNTS ||--o{ TRANSACTIONS : records
    STOCK_PRICES ||--o{ HOLDINGS : held_as
    STOCK_PRICES ||--o{ TRANSACTIONS : traded_as

    %% Table: users
    USERS {
        bigserial id PK
        text email
        text name
        bool active
        timestamptz created_at
    }

    %% Table: portfolios
    PORTFOLIOS {
        bigserial id PK
        bigint user_id FK
        bool active
        text name
        text description
        boolean is_default
        timestamptz created_at
    }

    %% Table: broker_types
    BROKER_TYPES {
        bigserial id PK
        text code
        text display_name
    }

    %% Table: broker_accounts
    BROKER_ACCOUNTS {
        bigserial id PK
        bigint portfolio_id FK
        bigint broker_type_id FK
        text external_account_id
        text display_name
        text status
        timestamptz created_at
    }

    %% Table: broker_account_credentials
    BROKER_ACCOUNT_CREDENTIALS {
        bigserial id PK
        bigint broker_account_id FK
        jsonb credentials
        boolean encrypted
        timestamptz created_at
        timestamptz updated_at
    }

    %% New Table: stock_prices (Stock model)
    STOCK_PRICES {
        bigserial id PK
        text symbol
        text isin
        text asset_type        %% equity, etf, etc.
        timestamptz as_of      %% price as-of timestamp
        numeric last_price
        numeric close_price
        timestamptz received_at
    }

    %% Table: holdings (now references stock)
    HOLDINGS {
        bigserial id PK
        bigint broker_account_id FK
        bigint stock_id FK
        numeric quantity
        numeric avg_price
        text currency
        timestamptz as_of
        text source_snapshot_id
        jsonb meta
        timestamptz created_at
    }

    %% Table: transactions (now references stock)
    TRANSACTIONS {
        bigserial id PK
        bigint broker_account_id FK
        bigint stock_id FK
        numeric quantity
        numeric price
        text currency
        text trade_type
        timestamptz trade_time
        jsonb meta
        timestamptz created_at
    }
