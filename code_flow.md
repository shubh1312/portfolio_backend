# Portfolio App — Code Flow, HLD & LLD

> This document explains how the code flows through the main parts of the project (Flask + Celery), shows diagrams, and describes High-Level Design (HLD) and Low-Level Design (LLD).

---
## Table of Contents
1. Overview (short)
2. Component diagram
3. Sequence diagram for `sync_holdings` flow
4. Files & responsibilities (map of file → role)
5. HLD (High-level design)
6. LLD (Low-level design — key functions, classes, and DB interactions)
7. Typical developer workflow (how to add a new broker trigger)
8. Troubleshooting checklist

---
## 1. Overview (short)
The portfolio project is a Flask application that maintains user portfolios and broker holdings, updates them periodically using Celery tasks, and supports pluggable **broker triggers** to fetch holdings from different broker providers (Zerodha, Vested, etc.).

Key runtime pieces:
- **Flask**: web server, admin interface, models, API routes.
- **SQLAlchemy**: ORM for models.
- **Celery**: background job processing; workers execute tasks; beat schedules tasks.
- **Redis**: message broker for Celery.
- **Flower**: monitoring UI for workers and tasks.
- **Triggers**: small pluggable modules that implement broker-specific fetch logic.

---
## 2. Component Diagram (ASCII)

```
┌─────────────────────────────────────────────────────────────────┐
│                         PORTFOLIO SYSTEM                         │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────┐
│   Flask App      │
│  (Web + Admin)   │
└────────┬─────────┘
         │
         ├─────────────────► PostgreSQL DB
         │
         └─────────────────► Celery Beat Scheduler
                                    │
                                    ▼
                            ┌──────────────┐
                            │ Redis Broker │
                            └──────┬───────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │  Celery Worker(s)   │
                        └─────────┬───────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
            ┌──────────────┐ ┌─────────────┐ ┌──────────┐
            │ Triggers     │ │ Sync Job    │ │ Update   │
            │ Registry     │ │ Management  │ │ DB       │
            │              │ │ Command     │ │ Models   │
            └──────┬───────┘ └─────────────┘ └──────────┘
                   │
         ┌─────────┴──────────┬──────────────┐
         │                    │              │
         ▼                    ▼              ▼
    Zerodha API          Vested API    Other Broker APIs
```

---
## 3. Sequence Diagram for `sync_holdings` Flow

```
Sequence: sync_holdings task execution

1. Celery Beat triggers sync_holdings_task()
   │
2. Task enqueued to Redis Broker
   │
3. Celery Worker receives task
   │
4. Worker calls management command: sync_holdings
   │
5. Command queries active portfolios & broker accounts from DB
   │
6. For each broker account:
   │
   6.1 → Get trigger from registry (e.g., ZerodhaTrigger)
   6.2 → Instantiate trigger with broker_account credentials
   6.3 → Call trigger.fetch_holdings() 
         (trigger makes API call to broker)
   6.4 ← Receive holdings snapshot list
   6.5 → Update/create Holding records in DB
   │
7. Command completes
   │
8. Task marked complete in Redis
   │
9. Flower displays execution history
```

---
## 4. Files & Responsibilities

| File | Responsibility |
|------|-----------------|
| `app/models/user.py` | User model: username, email, created_at |
| `app/models/portfolio.py` | Portfolio model: user, name, active status |
| `app/models/broker_type.py` | BrokerType: name, code (e.g., 'ZERODHA'), API docs |
| `app/models/broker_account.py` | BrokerAccount: portfolio, broker_type, account_id |
| `app/models/broker_account_credential.py` | BrokerAccountCredential: broker_account, encrypted credentials |
| `app/models/holding.py` | Holding: broker_account, symbol, quantity, avg_price |
| `app/models/transaction.py` | Transaction: holding, buy/sell, date, quantity, price |
| `app/admin/` | Flask-Admin views for models |
| `app/triggers/registry.py` | Registry dict & functions: `register()`, `get_trigger_for_code()` |
| `app/triggers/base.py` | BaseTrigger abstract class: `fetch_holdings()` interface |
| `app/triggers/zerodha.py` | ZerodhaTrigger: implements broker-specific API calls |
| `app/triggers/vested.py` | VestedTrigger: implements Vested API calls |
| `app/api/sync_routes.py` | Flask route handlers for sync operations (manual trigger) |
| `app/tasks.py` | Celery tasks: `sync_holdings_task()` |
| `app/celery_app.py` | Celery app configuration & autodiscovery |
| `.env` | Environment variables: DATABASE_URL, CELERY_BROKER_URL, etc. |

---
## 5. High-Level Design (HLD)

### Goal
Periodically sync user portfolios with external broker accounts in a pluggable, extensible way; keep the system maintainable, secure (encrypted credentials), and provide admin control & monitoring.

### Main HLD Components

**Web/Admin Layer (Flask)**
- CRUD operations for users, portfolios, broker accounts, credentials
- Flask-Admin interface for data management
- API routes for manual sync triggers

**Scheduler (Celery Beat)**
- Periodically enqueues `sync_holdings_task()`
- Can be configured via environment variables or Redis

**Task Processing (Celery Workers)**
- Execute `sync_holdings_task()`
- Call sync logic to fetch and update holdings
- Report results & errors

**Triggers Layer (Pluggable)**
- Broker-specific modules implementing standard `BaseTrigger` interface
- Registry maps broker codes (e.g., 'ZERODHA') to trigger classes
- Each trigger handles auth and API calls for its broker

**Persistence (PostgreSQL)**
- Canonical source for holdings, transactions, user portfolios
- Credentials stored with encrypted flag (ready for encryption)

**Monitoring (Flower)**
- Real-time view of worker status & task history
- Task error logs and retry information

### Design Principles
- **Pluggable adapter pattern**: Easy to add new brokers
- **Separation of concerns**: API logic in triggers, orchestration in commands, scheduling in Celery
- **Idempotent updates**: Use `update_or_create` to avoid duplicates
- **Secure by default**: Credentials marked for encryption
- **Observability**: Logs, error tracking, Flower monitoring

---
## 6. Low-Level Design (LLD)

### Key Classes & Functions

#### `app/triggers/registry.py`
```python
REGISTRY = {}

def register(code):
    """Decorator to register a trigger with a broker code."""
    def _inner(cls):
        REGISTRY[code] = cls
        return cls
    return _inner

def get_trigger_for_code(code):
    """Retrieve trigger class by broker code."""
    return REGISTRY.get(code)
```

#### `app/triggers/base.py`
```python
from abc import ABC, abstractmethod

class BaseTrigger(ABC):
    def __init__(self, broker_account):
        self.broker_account = broker_account

    @abstractmethod
    def fetch_holdings(self):
        """
        Fetch holdings from broker API.
        Returns: list of dicts with keys:
          - symbol, quantity, avg_price, asset_type, ...
        """
        raise NotImplementedError
```

#### `app/triggers/zerodha.py` (Example)
```python
from .registry import register
from .base import BaseTrigger
import kiteconnect  # Zerodha API library

@register('ZERODHA')
class ZerodhaTrigger(BaseTrigger):
    def fetch_holdings(self):
        creds = self.broker_account.credential.credentials
        # Assuming creds is JSON: {"api_key": "...", "access_token": "..."}
        kite = kiteconnect.KiteConnect(api_key=creds['api_key'])
        kite.set_access_token(creds['access_token'])
        
        holdings = kite.holdings()
        result = []
        for h in holdings:
            result.append({
                'symbol': h['tradingsymbol'],
                'quantity': h['quantity'],
                'avg_price': h['average_price'],
                'asset_type': h['instrument_type'],
                'as_of': datetime.now(),
            })
        return result
```

#### `app/tasks.py`
```python
from celery import shared_task
from django.core.management import call_command

@shared_task(bind=True, max_retries=3)
def sync_holdings_task(self):
    """
    Celery task wrapper for sync_holdings management command.
    Retries up to 3 times on failure.
    """
    try:
        call_command('sync_holdings')
    except Exception as exc:
        self.retry(exc=exc, countdown=60)  # Retry in 60 seconds
```

#### Sync Logic (Management Command or Service)
Pseudo-code:
```python
def sync_holdings():
    portfolios = Portfolio.query.filter_by(active=True).all()
    
    for portfolio in portfolios:
        for account in portfolio.broker_accounts:
            trigger_cls = get_trigger_for_code(account.broker_type.code)
            
            if not trigger_cls:
                log.warning(f"No trigger for {account.broker_type.code}")
                continue
            
            try:
                trigger = trigger_cls(account)
                snapshot = trigger.fetch_holdings()
                
                # Update DB
                for holding_data in snapshot:
                    Holding.query.update_or_create(
                        broker_account_id=account.id,
                        symbol=holding_data['symbol'],
                        defaults={
                            'quantity': holding_data['quantity'],
                            'avg_price': holding_data['avg_price'],
                            'as_of': holding_data['as_of'],
                        }
                    )
                    db.session.commit()
                    
            except AuthError:
                account.active = False
                db.session.commit()
                log.error(f"Auth failed for {account.id}")
            except Exception as exc:
                log.error(f"Sync failed for {account.id}: {exc}")
                raise
```

### Database Schema (Key Relations)
```
User (1) ──────────► (N) Portfolio
Portfolio (1) ──────────► (N) BrokerAccount
BrokerAccount (1) ──────────► (1) BrokerAccountCredential
BrokerAccount (1) ──────────► (N) Holding
BrokerAccount (1) ──────────► (N) Transaction
```

### Error Handling & Retries
- **Transient errors** (network, timeout): Retry with exponential backoff
- **Auth errors**: Mark broker account inactive, alert user
- **Invalid symbol**: Log warning, skip, continue processing
- **DB errors**: Rollback transaction, retry entire sync

---
## 7. Typical Developer Workflow (Add New Broker Trigger)

### Step 1: Create trigger file
```bash
touch app/triggers/mybroker.py
```

### Step 2: Implement trigger class
```python
# app/triggers/mybroker.py
from .registry import register
from .base import BaseTrigger

@register('MYBROKER')
class MyBrokerTrigger(BaseTrigger):
    def fetch_holdings(self):
        # Get credentials
        creds = self.broker_account.credential.credentials
        # creds is JSON dict with auth info
        
        # Make API call to broker
        response = requests.get(
            'https://api.mybroker.com/holdings',
            headers={'Authorization': f"Bearer {creds['access_token']}"}
        )
        response.raise_for_status()
        
        # Parse response into standard format
        holdings = []
        for item in response.json()['data']:
            holdings.append({
                'symbol': item['ticker'],
                'quantity': item['shares'],
                'avg_price': item['cost_basis'],
                'asset_type': 'stock',
                'as_of': datetime.now(),
            })
        
        return holdings
```

### Step 3: Register broker type in admin or code
```python
# In Flask shell or management command
broker_type = BrokerType.create(name='MyBroker', code='MYBROKER')
db.session.commit()
```

### Step 4: Test trigger
```bash
# Test management command locally
python -m app.cli sync_holdings

# Or in Python shell
from app.triggers.registry import get_trigger_for_code
from app.models import BrokerAccount
account = BrokerAccount.query.first()
trigger_cls = get_trigger_for_code('MYBROKER')
trigger = trigger_cls(account)
holdings = trigger.fetch_holdings()
print(holdings)

# Or enqueue Celery task
from app.tasks import sync_holdings_task
result = sync_holdings_task.delay()
result.get()  # Wait for result
```

### Step 5: Deploy
- Restart Celery workers to pick up new code
- Monitor Flower for task execution
- Check logs for errors

---
## 8. Troubleshooting Checklist

| Issue | Solution |
|-------|----------|
| **ImportError in registry** | Ensure `app/triggers/__init__.py` imports registry & triggers |
| **No trigger found** | Check `BrokerType.code` matches `@register('CODE')` exactly |
| **Task PENDING in Flower** | Verify Celery worker is running: `celery -A app.celery_app worker -l info` |
| **Credentials missing** | Ensure `BrokerAccountCredential` exists & `broker_account.credential` is set |
| **API auth fails** | Check credentials are fresh; test API directly with same creds |
| **Holdings not updating** | Check DB connection; verify `update_or_create` logic; inspect logs |
| **Worker crashes on import** | Run `python -m app.triggers.zerodha` to catch import errors |
| **Stale holdings in DB** | Check `as_of` timestamp; verify sync is actually running |

---
## Appendix: Tips & Next Steps

### Development
- Use `celery -A app.celery_app events` to see live task events
- Use `celery -A app.celery_app inspect active` to see running tasks
- Set `CELERY_TASK_ALWAYS_EAGER=True` in development to run tasks synchronously

### Production
- Use `supervisord` or `systemd` to manage workers
- Enable task result backend (e.g., django-celery-results) for persistent task history
- Monitor Redis memory usage; set appropriate `maxmemory` policy
- Set up alerts for task failures via Flower webhooks or custom error handlers

### Performance
- Batch holdings updates per broker_account to reduce DB transactions
- Implement caching for broker metadata (symbols, asset types)
- Use connection pooling for API calls (requests.Session)
- Consider AsyncIO for concurrent API calls if broker supports it

---
*Document: Portfolio App HLD/LLD — Flask + SQLAlchemy + Celery*
