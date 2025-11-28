# Portfolio App — Code Flow, HLD & LLD

> This document explains how the code flows through the main parts of the project (Django + Celery + Triggers), shows diagrams (Mermaid + ASCII fallback), and describes High-Level Design (HLD) and Low-Level Design (LLD).

---
## Table of contents
1. Overview (short)
2. Component diagram (Mermaid + ASCII fallback)
3. Sequence diagram for `sync_holdings` flow (Mermaid + ASCII)
4. Files & responsibilities (map of file → role)
5. HLD (High-level design)
6. LLD (Low-level design — key functions, classes, and DB interactions)
7. Typical developer workflow (how to add a new broker trigger)
8. Troubleshooting checklist
9. Appendix — mermaid notes / how to view diagrams

---
## 1. Overview (short)
The portfolio project is a Django application that maintains user portfolios and broker holdings, updates them periodically using Celery tasks, and supports pluggable **broker triggers** to fetch holdings from different broker providers (Zerodha, INDmoney, etc.).

Key runtime pieces:
- **Django**: web server, admin, models, management commands.
- **Celery**: background job processing; workers execute tasks; beat schedules tasks.
- **Redis**: message broker for Celery.
- **django-celery-beat**: optional DB-driven scheduler (manage periodic tasks from admin).
- **Flower**: monitoring UI for workers and tasks.
- **Triggers**: small pluggable modules that implement broker-specific fetch logic.

---
## 2. Component diagram (Mermaid)

```mermaid
graph LR
  A[Django App (HTTP / Admin)] -->|creates/edits| DB[(Postgres DB)]
  DB -->|data| A
  A -->|schedules task| CeleryBeat[Celery Beat / django-celery-beat]
  CeleryBeat -->|sends task| Redis[(Redis Broker)]
  Redis -->|queue| CeleryWorker[Celery Worker(s)]
  CeleryWorker -->|calls| ManagementCmd[sync_holdings management command]
  ManagementCmd -->|reads| DB
  ManagementCmd -->|loads triggers| TriggersPackage[portfolio.triggers]
  TriggersPackage -->|calls| TriggerImpls[Broker-specific triggers]
  TriggerImpls -->|fetch data| BrokerAPIs[Broker APIs (Zerodha, Vested...)]
  BrokerAPIs -->|return snapshot| TriggerImpls
  TriggerImpls -->|return list| ManagementCmd
  ManagementCmd -->|update/create| HoldingModel[Holding model in DB]
  Flower -->|monitors| CeleryWorker
  CeleryWorker -->|reports results| CeleryResults[(django-celery-results / DB)]
```

**ASCII fallback:**
```
[Django Admin] <---> [Postgres DB]
      |
      v
[Celery Beat] ---> Redis Broker ---> [Celery Worker(s)] ---> sync_holdings management command
                                                        |-> portfolio.triggers.registry -> trigger impls -> Broker APIs
                                                        |-> update Holding / Transaction models in DB
Flower watches workers and tasks; django-celery-beat lets Admin edit schedules (stored in DB).
```

---
## 3. Sequence diagram for `sync_holdings` flow (Mermaid)

```mermaid
sequenceDiagram
  autonumber
  participant Beat as Celery Beat / Scheduler
  participant Redis as Redis Broker
  participant Worker as Celery Worker
  participant Cmd as sync_holdings (management command)
  participant Registry as portfolio.triggers.registry
  participant Trigger as TriggerImpl (e.g., ZerodhaTrigger)
  participant Broker as Broker API
  participant DB as Postgres DB (Django models)
  Beat->>Redis: enqueues sync_holdings task (or Beat triggers stored DB schedule)
  Redis->>Worker: delivers task
  Worker->>Cmd: call_command('sync_holdings')
  Cmd->>DB: Query active portfolios & broker_accounts
  loop per broker account
    Cmd->>Registry: get_trigger_for_code(broker_type.code)
    Registry-->>Cmd: Trigger class (or None)
    Cmd->>Trigger: instantiate(trigger, broker_account)
    Trigger->>Broker: API call (auth via broker_account.credential.credentials)
    Broker-->>Trigger: holdings snapshot list
    Trigger-->>Cmd: returns snapshot list
    Cmd->>DB: update_or_create Holding rows for snapshot
  end
  Cmd-->>Worker: finished; returns results
  Worker->>Redis: task completed (result stored / acked)
  Worker->>Flower: worker events visible in Flower
```

**ASCII fallback:**
```
[Beat] -> Redis (task queued)
Redis -> Worker (task delivered)
Worker -> run sync_holdings (calls management command)
management command:
  - Query active portfolios
  - For each portfolio: for each broker account:
      - get trigger for broker type via registry
      - instantiate trigger with broker account (and credentials)
      - call trigger.fetch_holdings() -> trigger calls broker API
      - receive snapshot list -> update DB (Holding objects)
  - done
Worker marks task done; Flower shows execution history.
```

---
## 4. Files & responsibilities (map)

- `portfolio/models.py` — Django ORM models: `User`, `Portfolio`, `BrokerType`, `BrokerAccount`, `BrokerAccountCredential`, `Holding`, `Transaction`.
- `portfolio/admin.py` — Admin site registrations for models.
- `portfolio/triggers/registry.py` — Simple registry: `REGISTRY` dict, `register(code)` decorator, and `get_trigger_for_code(code)` function.
- `portfolio/triggers/base.py` — `BaseTrigger` abstract base class: defines `fetch_holdings()` signature.
- `portfolio/triggers/<broker>.py` — broker-specific triggers (e.g., `sample_zerodha.py`) that implement `BaseTrigger` and register with `@register('ZERODHA')`.
- `portfolio/management/commands/sync_holdings.py` — management command that actually pulls data using triggers and writes to DB. When run in Celery, the task calls `call_command('sync_holdings')`.
- `portfolio/tasks.py` — Celery task wrappers. `@shared_task` functions such as `sync_holdings_task` that Celery workers execute (they call the management command).
- `portfolio_project/celery.py` — Celery app config and autodiscovery.
- `django-celery-beat` models (installed app) — DB-driven scheduler; Admin UI to manage `PeriodicTask`, `CrontabSchedule`.
- `Flower` — an external monitoring UI (not part of Django) that connects to the same broker to display worker status & task history.
- `.env` / settings — define `DATABASE_URL`, `CELERY_BROKER_URL`, and other runtime configs.

---
## 5. High-Level Design (HLD)

**Goal:** Periodically sync user portfolios with external broker accounts in a pluggable, extensible way; keep system maintainable and secure (credentials encrypted in DB), and provide admin control & monitoring.

### Main HLD components:
- **Web / Admin Layer (Django):** CRUD for users, portfolios, accounts and credentials. Manage periodic tasks via `django-celery-beat` in admin.
- **Scheduler (Celery Beat):** Uses DB or in-memory schedules to enqueue `sync_holdings` tasks.
- **Task Processing (Celery Workers):** Execute `sync_holdings_task` and call the management command or internal service to sync holdings.
- **Triggers Layer (Pluggable):** Broker-specific modules implementing a standard interface. Registration via decorator maps broker codes to trigger classes.
- **Persistence (Postgres):** Stores canonical holdings snapshot and transactions.
- **Monitoring (Flower / Admin):** Observe task health & adjust schedules.

**Design principles:**
- Pluggable adapter pattern for broker integrations.
- Separation of concerns: API fetch logic in triggers, business orchestration in management command, scheduling in Celery.
- Idempotent updates: use `update_or_create` to avoid duplicate holdings.
- Secure credential storage: mark `encrypted` flag and plan for encryption.

---
## 6. Low-Level Design (LLD)

LLD describes the concrete modules, classes, and method-level interactions.

### Key classes & functions

#### `portfolio.triggers.registry`
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

#### `portfolio.triggers.base.BaseTrigger`
```python
class BaseTrigger(ABC):
    def __init__(self, broker_account):
        self.broker_account = broker_account

    @abstractmethod
    def fetch_holdings(self):
        raise NotImplementedError
```

#### `portfolio/triggers/sample_zerodha.ZerodhaTrigger`
- Implements `fetch_holdings()` and returns list of dicts:
  ```py
  [
    { 'symbol': 'TCS', 'quantity': 10, 'avg_price': 2200.0, 'asset_type': 'stock', ... },
    ...
  ]
  ```

#### `portfolio/management/commands/sync_holdings.py` (core loop)
Pseudo:
```py
portfolios = Portfolio.objects.filter(active=True)
for p in portfolios:
    for account in p.broker_accounts.all().select_related('broker_type'):
        trigger_cls = registry.get_trigger_for_code(account.broker_type.code)
        if not trigger_cls:
            continue
        trigger = trigger_cls(account)
        snapshot = trigger.fetch_holdings()
        for h in snapshot:
            Holding.objects.update_or_create(
                broker_account=account, symbol=h['symbol'], as_of=h.get('as_of', now),
                defaults={...}
            )
```

#### `portfolio/tasks.py`
Celery task wrapper:
```py
@shared_task(bind=True)
def sync_holdings_task(self):
    call_command('sync_holdings')
```

### DB interactions
- `Portfolio` → `BrokerAccount` (1:N)
- `BrokerAccount` → `BrokerAccountCredential` (1:1)
- `BrokerAccount` → `Holding` (1:N)
- `BrokerAccount` → `Transaction` (1:N)

Holding updates use `update_or_create` keyed by `(broker_account, symbol, as_of)` (or just `symbol` depending on uniqueness choice).

### Error handling & retries
- Celery task retries can be configured with decorators or within the management command.
- Each trigger should raise specific exceptions on auth error vs transient network error so the management command can decide to retry or mark the account disabled.

---
## 7. Typical developer workflow (add new broker trigger)

1. Create new file `portfolio/triggers/mybroker.py`.
2. Implement a class:
```py
from .registry import register
from .base import BaseTrigger

@register('MYBROKER')
class MyBrokerTrigger(BaseTrigger):
    def fetch_holdings(self):
        creds = self.broker_account.credential.credentials
        # perform API calls, parse response, return list of holdings dicts
        return [...]
```
3. Restart worker processes (to pick up new modules) and test via Django shell or by calling the management command directly:
```bash
python manage.py sync_holdings
# or enqueue via celery
python manage.py shell
>>> from portfolio.tasks import sync_holdings_task
>>> sync_holdings_task.delay()
```

---
## 8. Troubleshooting checklist (common issues)

- **ImportError referencing registry**: Ensure `portfolio/triggers/__init__.py` exports registry correctly.
- **Task received but failed**: Inspect worker logs; run management command locally to reproduce exception.
- **No trigger found for broker code**: Check `BrokerType.code` matches decorator `@register('CODE')`.
- **Credentials missing**: Ensure `BrokerAccountCredential` exists and `broker_account.credential` relation is present.
- **Beat not firing**: Confirm `celery beat` is running and you used `DatabaseScheduler`.
- **Flower shows tasks PENDING**: Worker not connected, mismatched broker, or queue routing issue.

---
## 9. Appendix — mermaid notes / how to view diagrams

- The file includes Mermaid diagrams. Some Markdown viewers (GitHub, GitLab, VSCode with Mermaid preview) render them automatically.
- If your viewer doesn't render mermaid, use an online mermaid live editor (https://mermaid.live/) and paste the mermaid code blocks.
- ASCII fallbacks are included immediately below each mermaid block for quick viewing in plain-text environments.

---
*Document generated by ChatGPT — detailed to help you understand code flow, HLD and LLD. If you want, I can convert these diagrams to PNG/SVG files and include them in a zip.*
