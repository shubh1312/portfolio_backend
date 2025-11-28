# Database Schema ER Diagram

```mermaid
erDiagram
    USERS ||--o{ PORTFOLIOS : owns
    PORTFOLIOS ||--o{ BROKER_ACCOUNTS : owns
    BROKER_TYPES ||--o{ BROKER_ACCOUNTS : categorizes
    BROKER_ACCOUNTS ||--|| BROKER_ACCOUNT_CREDENTIALS : has
    BROKER_ACCOUNTS ||--o{ HOLDINGS : contains
    BROKER_ACCOUNTS ||--o{ TRANSACTIONS : records

    %% Table: users
    USERS {
        bigserial id PK
        text email
        text name
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

    %% Table: holdings
    HOLDINGS {
        bigserial id PK
        bigint broker_account_id FK
        text asset_type
        text symbol
        text isin
        numeric quantity
        numeric avg_price
        text currency
        numeric cost_value
        numeric market_value
        timestamptz as_of
        text source_snapshot_id
        jsonb meta
        timestamptz created_at
    }

    %% Table: transactions
    TRANSACTIONS {
        bigserial id PK
        bigint broker_account_id FK
        text asset_type
        text symbol
        numeric quantity
        numeric price
        text currency
        text trade_type
        timestamptz trade_time
        jsonb meta
        timestamptz created_at
    }
