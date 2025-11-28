# Portfolio App — Code Flow, HLD & LLD (Updated)

> This document explains how the code flows through the project (Django + Celery), shows diagrams, and describes High-Level Design (HLD) and Low-Level Design (LLD). It has been updated to reflect the new **service layer**, **task split** (dispatcher, portfolio, broker), django-celery-beat, Flower, and the pluggable trigger design.

---
## Table of Contents
1. Overview (short)
2. Component diagram (Mermaid + ASCII)
3. Sequence diagrams
   - 3.1 Full scheduled flow (dispatcher → portfolio → broker)
   - 3.2 Single portfolio synchronous call (services)
4. Files & responsibilities (map of file → role)
5. HLD (High-level design)
6. LLD (Low-level design — key functions, classes, and DB interactions)
7. Developer workflow (how to add a new broker trigger)
8. Operational guidance (queues, retries, rate-limits, monitoring)
9. Troubleshooting checklist
10. Quick start / commands (migrate, run workers, create periodic task)
11. Appendix — examples (trigger example, sample tasks signatures)

---
## 1. Overview (short)
This Django-based portfolio project synchronizes user portfolios and broker holdings using a scalable, testable architecture. It uses:

- **Django** for the web/admin API (models, admin, management commands)
- **Celery** for background processing (workers, beat, tasks)
- **Redis** as the Celery broker (and optionally result backend)
- **django-celery-beat** for DB-driven periodic schedules (editable in Admin)
- **Flower** for monitoring workers and task history
- **Triggers**: pluggable broker adapters (Zerodha, Vested...) that implement API calls and normalize responses
- **services.py**: core synchronous business logic used by tasks and commands

Key idea: one scheduled dispatcher fans out tasks per-portfolio and per-broker; each worker is small and calls `services.py` to perform real DB updates so logic is reusable & testable.

---
## 2. Component diagram (Mermaid + ASCII)

```mermaid
graph LR
  Web[Django (Web + Admin)] -->|CRUD / Schedule| DB[(Postgres)]
  Web -->|create PeriodicTask| CeleryBeat[(django-celery-beat)]
  CeleryBeat -->|enqueue| Redis[(Redis Broker)]
  Redis -->|deliver| Worker[Celery Worker(s)]
  Worker -->|orchestrates| Dispatcher[dispatcher_task]
  Dispatcher -->|enqueue| PortfolioTask[portfolio_task (per-portfolio)]
  PortfolioTask -->|group| BrokerTask[broker_action_task (per-broker)]
  BrokerTask -->|calls| TriggerPkg[portfolio.triggers]
  TriggerPkg -->|HTTP| BrokerAPI[Broker APIs (Zerodha, Vested...)]
  BrokerTask -->|persist| Services[portfolio.services.persist_*]
  Services -->|write| DB
  Flower -->|monitor| Worker
```
**ASCII fallback:**
```
[Django Admin] --> Postgres
     |
     --> Celery Beat (django-celery-beat) -> Redis -> Celery Workers
           Dispatcher task -> enqueues per-portfolio tasks
           Portfolio tasks -> group enqueues per-broker tasks
           Broker tasks -> call trigger.fetch_xxx() -> services.persist_xxx() -> DB
Flower watches workers & tasks
```

---
## 3. Sequence diagrams

### 3.1 Full scheduled flow (dispatcher → portfolio → broker)
```
1. django-celery-beat (or cron) triggers active_users_data_sync_worker (dispatcher)
2. dispatcher queries DB for active users -> active portfolios
3. dispatcher enqueues portfolio_sync_task(portfolio_id) for each active portfolio
4. Celery worker picks up portfolio_sync_task
5. portfolio_sync_task builds a group of broker_action_task.s(portfolio_id, broker_account_id, action)
6. Celery executes the group in parallel: worker(s) run broker_action_task for each broker account
7. Each broker_action_task:
   a. loads BrokerAccount and credentials
   b. resolves trigger class from registry (by broker_type.code)
   c. instantiates trigger(account)
   d. calls trigger.fetch_holdings() or trigger.fetch_transactions() — **API call happens here**
   e. passes normalized list to services.persist_holdings(account, data)
   f. services.persist_holdings() writes holdings to DB in a transaction
8. portfolio_task optionally waits for group completion (using chord) and triggers postprocess (recompute totals)
9. Task results and events are visible in Flower and result backend
```

### 3.2 Single portfolio synchronous call (no Celery)
```
Developer/Admin/Test calls:
from portfolio.services import sync_portfolio_holdings
p = Portfolio.objects.get(id=123)
sync_portfolio_holdings(p)   # runs synchronously: triggers -> services -> DB
```
This is used for debugging, unit tests, manual sync, or inside management commands without Celery.

---
## 4. Files & responsibilities (map)

| Path | Responsibility |
|------|----------------|
| `portfolio/models.py` | Django models (User, Portfolio, BrokerType, BrokerAccount, Credential, Holding, Transaction) |
| `portfolio/admin.py` | Django Admin registrations |
| `portfolio/triggers/registry.py` | REGISTRY, `register(code)` decorator, `get_trigger_for_code` |
| `portfolio/triggers/base.py` | `BaseTrigger` abstract class signature (fetch_holdings, fetch_transactions) |
| `portfolio/triggers/<broker>.py` | Broker adapter implementations — API calls + normalization |
| `portfolio/services.py` | Pure-Python business logic: `persist_holdings`, `sync_portfolio_holdings`, helpers |
| `portfolio/tasks/dispatcher.py` | `active_users_data_sync_worker` — scheduled dispatcher task |
| `portfolio/tasks/portfolio.py` | `portfolio_sync_task` — fans out per-broker tasks |
| `portfolio/tasks/broker.py` | `broker_action_task` — calls trigger methods and delegates DB writes to services |
| `portfolio/management/commands/sync_holdings.py` | Management command to run sync (all or single portfolio) |
| `portfolio_project/celery.py` | Celery app config & autodiscovery |
| `requirements.txt` | celery, redis, django-celery-beat, django-celery-results, flower, requests, psycopg2-binary |
| `README.md` | Setup & run instructions (db, env, celery worker, beat, flower) |

---
## 5. High-Level Design (HLD)

### Purpose
Keep the system modular and scalable: orchestrate work via Celery, implement reusable business logic in `services.py`, implement broker-specific API logic in triggers, and provide admin control via django-celery-beat.

### Responsibilities
- **Dispatcher**: one scheduled job (Active users → portfolios) that fans-out work.
- **Portfolio Task**: groups broker tasks for a portfolio (parallelizes per-broker work).
- **Broker Task**: executes broker-specific calls (via triggers) and delegates persistence to services.
- **Services**: contain logic to persist holdings/transactions atomically and compute derived fields.
- **Triggers**: adapter layer to talk to broker APIs and normalize responses.

### Non-functional goals
- **Scalability**: fan-out model lets many workers process portfolios concurrently.
- **Observability**: Flower + logs + result backend + structured task metadata.
- **Testability**: services are pure-Python and testable synchronously.
- **Resilience**: retries, error isolation, marking accounts disabled on auth failures.

---
## 6. Low-Level Design (LLD)

### Key functions & examples

#### `portfolio/triggers/registry.py`
```python
REGISTRY = {}

def register(code):
    def _inner(cls):
        REGISTRY[code] = cls
        return cls
    return _inner

def get_trigger_for_code(code):
    return REGISTRY.get(code)
```

#### `portfolio/triggers/base.py`
```python
from abc import ABC, abstractmethod

class BaseTrigger(ABC):
    def __init__(self, broker_account):
        self.broker_account = broker_account

    @abstractmethod
    def fetch_holdings(self):
        pass

    def fetch_transactions(self, since=None):
        raise NotImplementedError
```

#### `portfolio/services.py` (key API)
```python
from django.utils import timezone
from django.db import transaction
from .models import Holding

def persist_holdings(broker_account, holdings_list):
    saved = 0
    with transaction.atomic():
        for item in holdings_list:
            obj, created = Holding.objects.update_or_create(
                broker_account=broker_account,
                symbol=item['symbol'],
                as_of=item.get('as_of', timezone.now()),
                defaults={
                    'asset_type': item.get('asset_type','stock'),
                    'isin': item.get('isin'),
                    'quantity': item.get('quantity',0),
                    'avg_price': item.get('avg_price',0),
                    'currency': item.get('currency','INR'),
                    'cost_value': item.get('cost_value'),
                    'market_value': item.get('market_value'),
                    'meta': item.get('meta'),
                }
            )
            saved += 1
    return saved

def sync_portfolio_holdings(portfolio):
    # loops accounts and uses triggers + persist_holdings
    ...
```
(Full implementation lives in `portfolio/services.py` file)

#### `portfolio/tasks/broker.py`
```python
from celery import shared_task
from django.apps import apps
from portfolio.triggers import registry
from portfolio.services import persist_holdings

ACTION_HANDLERS = {'holdings': 'fetch_holdings', 'transactions': 'fetch_transactions'}

@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def broker_action_task(self, portfolio_id, broker_account_id, action):
    BrokerAccount = apps.get_model('portfolio', 'BrokerAccount')
    acc = BrokerAccount.objects.select_related('broker_type','credential').get(id=broker_account_id)
    trigger_cls = registry.get_trigger_for_code(acc.broker_type.code)
    trigger = trigger_cls(acc)
    data = getattr(trigger, ACTION_HANDLERS[action])()
    saved = persist_holdings(acc, data)
    return {'status':'ok','saved':saved}
```

#### `portfolio/tasks/portfolio.py` (fanning out)
```python
from celery import shared_task, group
from django.apps import apps
from portfolio.tasks.broker import broker_action_task

@shared_task(bind=True)
def portfolio_sync_task(self, portfolio_id, actions=None):
    Portfolio = apps.get_model('portfolio','Portfolio')
    p = Portfolio.objects.get(id=portfolio_id)
    actions = actions or ['holdings']
    sigs = [broker_action_task.s(portfolio_id, acc.id, action) for acc in p.broker_accounts.all() for action in actions]
    if not sigs: return {'status':'no_brokers'}
    job = group(sigs).apply_async()
    return {'group_id':job.id,'tasks':len(sigs)}
```

#### `portfolio/tasks/dispatcher.py` (scheduled)
```python
from celery import shared_task
from django.apps import apps
from portfolio.tasks.portfolio import portfolio_sync_task

@shared_task(bind=True)
def active_users_data_sync_worker(self):
    User = apps.get_model('portfolio','User')
    Portfolio = apps.get_model('portfolio','Portfolio')
    for uid in User.objects.filter(active=True).values_list('id',flat=True):
        pids = Portfolio.objects.filter(user_id=uid, active=True).values_list('id', flat=True)
        for pid in pids:
            portfolio_sync_task.delay(pid)
    return {'status':'dispatched'}
```

### DB interactions & constraints
- Use `update_or_create` to be idempotent for holdings snapshots.
- Consider unique constraints (broker_account, symbol, as_of) if required.
- Use GIN index on JSON meta fields if you query them often.

---
## 7. Developer workflow — Add new broker trigger (quick)

1. Create file `portfolio/triggers/mybroker.py`
2. Implement class and register:
```python
from .registry import register
from .base import BaseTrigger
import requests

@register('MYBROKER')
class MyBrokerTrigger(BaseTrigger):
    def fetch_holdings(self):
        creds = self.broker_account.credential.credentials
        resp = requests.get('https://api...', headers={ 'Authorization': f"Bearer {creds['token']}" })
        resp.raise_for_status()
        data = resp.json()['data']
        # normalize
        return [{'symbol': d['ticker'], 'quantity': d['qty'], 'avg_price': d['avg']} for d in data]
```
3. Add BrokerType in DB (admin or migration) with `code='MYBROKER'`
4. Restart Celery workers to pick up new module
5. Test via shell or management command

---
## 8. Operational guidance (queues, retries, rate-limits, monitoring)

### Queues & routing
- Use dedicated queues for rate-limited brokers: `broker_zerodha`, `broker_vested`
- Route tasks by name or set queue on signature: `broker_action_task.s(...).set(queue='broker_zerodha')`
- Start workers per-queue: `celery -A portfolio_project worker -Q broker_zerodha --concurrency=4`

### Retries
- Use `max_retries` and `default_retry_delay` for each broker task
- Distinguish retryable (network/timeouts) vs non-retryable (auth failure)

### Rate-limits & throttling
- Use Celery `rate_limit` per task or run low-concurrency workers for that queue
- Implement exponential backoff in triggers for HTTP 429 responses

### Monitoring & Observability
- Flower for live monitoring: `celery -A portfolio_project flower --port=5555`
- Use django-celery-results or a result backend to retain task metadata
- Structured logs: include `task_id`, `portfolio_id`, `broker_account_id`

### Security
- Encrypt sensitive credentials in DB (or use KMS)
- Do not log secrets; mask tokens in logs
- Use secure transport (HTTPS) and minimal privileges for API tokens

---
## 9. Troubleshooting checklist

- **No tasks executed**: ensure Celery worker is running and uses same broker URL
- **Tasks stuck PENDING**: worker not connected to broker or wrong queue routing
- **ImportError for triggers**: ensure `portfolio/triggers/__init__.py` exposes registry and imports modules
- **No trigger found for broker_code**: confirm BrokerType.code matches decorator string
- **Auth failures**: check token expiry and refresh flows in trigger implementation
- **Duplicate holdings**: re-evaluate uniqueness key; use `source_snapshot_id` to deduplicate
- **Slow performance**: batch DB writes, reduce transactions, or increase worker parallelism

---
## 10. Quick start & commands

```bash
# Activate venv
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Create DB & migrate
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run Django dev server
python manage.py runserver

# Start worker(s)
celery -A portfolio_project worker --loglevel=info

# Start beat (if using django-celery-beat)
celery -A portfolio_project beat --loglevel=info

# Start Flower (monitor)
celery -A portfolio_project flower --port=5555

# Create a sample DB-driven periodic task (if management command exists):
python manage.py create_sample_periodic_task

# Manually trigger a single-portfolio task (async)
python manage.py shell
>>> from portfolio.tasks.portfolio import portfolio_sync_task
>>> portfolio_sync_task.delay(1)   # portfolio id 1
```

---
## 11. Appendix — Examples

### Example trigger (Zerodha) — `portfolio/triggers/zerodha.py`
```python
from .registry import register
from .base import BaseTrigger
import requests, datetime

@register('ZERODHA')
class ZerodhaTrigger(BaseTrigger):
    def __init__(self, broker_account):
        super().__init__(broker_account)
        self.creds = broker_account.credential.credentials

    def fetch_holdings(self):
        headers = {'Authorization': f"Bearer {self.creds.get('access_token')}"}
        url = "https://api.kite.trade/portfolio/holdings"
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        now = datetime.datetime.now(datetime.timezone.utc)
        out = []
        for item in resp.json().get('data', []):
            out.append({
                'symbol': item['tradingsymbol'],
                'quantity': float(item['quantity']),
                'avg_price': float(item['average_price']),
                'asset_type': 'stock',
                'as_of': now,
                'source_snapshot_id': item.get('instrument_token'),
                'meta': item,
            })
        return out
```

### Example services functions (persist_holdings)
```python
def persist_holdings(broker_account, holdings_list):
    # Implementation shown earlier in LLD
    return saved_count
```

---
## Closing notes

This updated document reflects the recommended architecture: **dispatcher → portfolio → broker** task split, **services.py** as the canonical synchronous business layer, **triggers** as adapters for broker APIs, and operational best-practices for running Celery workers, beat, and Flower. Keep services pure and testable, tasks thin and orchestrating, and triggers focused on API handling & normalization.

If you want, I can:
- Convert the Mermaid diagrams into SVG/PNG images and attach them
- Generate a tidy ZIP with the updated `tasks/`, `services.py`, and example triggers patched into your repo
- Create sample `systemd` unit files for queue-specific workers and Flower

Which would you like next?
