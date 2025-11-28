erDiagram

    users ||--o{ portfolios : has
    portfolios ||--o{ broker_accounts : has
    broker_types ||--o{ broker_accounts : defines
    broker_accounts ||--|| broker_account_credentials : has
    broker_accounts ||--o{ holdings : has
    broker_accounts ||--o{ transactions : has

    users {
        bigserial id PK
        text email
        text name
        timestamptz created_at
    }

    portfolios {
        bigserial id PK 
        bigint user_id FK
        bool active
        text name
        text description
        boolean is_default
        timestamptz created_at
    }

    broker_types {
        bigserial id PK
        text code
        text display_name
    }

    broker_accounts {
        bigserial id PK
        bigint portfolio_id FK
        bigint broker_type_id FK
        text external_account_id
        text display_name
        text status
        timestamptz created_at
    }

    broker_account_credentials {
        bigserial id PK
        bigint broker_account_id FK
        jsonb credentials
        boolean encrypted
        timestamptz created_at
        timestamptz updated_at
    }

    holdings {
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

    transactions {
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
