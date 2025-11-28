# Portfolio Django Project (scaffold)

This repository is a ready-to-run Django project implementing the database schema you provided and:
- Models for users, portfolios, broker types/accounts/credentials, holdings, and transactions.
- Admin pages to view and manage data.
- A management command `sync_holdings` which acts as the worker entrypoint (suitable to call from cron).
- A pluggable triggers system: add trigger modules under `portfolio/triggers` and register them using the registry decorator.

---

## What's included
- Django project: `portfolio_project`
- App: `portfolio`
- Example trigger: `portfolio/triggers/sample_zerodha.py` (mocked)
- Management command: `python manage.py sync_holdings`

## Requirements
Python 3.9+ (recommended). See `requirements.txt`.

## Quick local setup (SQLite - easiest)
1. Create and activate a virtualenv:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Create `.env` file (project reads DB settings from it). For sqlite you can create a minimal `.env`:
   ```env
   DEBUG=True
   SECRET_KEY=dev-secret-key
   DATABASE_URL=sqlite:///db.sqlite3
   ```
3. Run migrations and create superuser:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```
4. Start dev server:
   ```bash
   python manage.py runserver
   ```
5. Open admin at http://127.0.0.1:8000/admin and log in. You'll be able to add BrokerTypes (e.g. ZERODHA) and create BrokerAccounts attached to Portfolios.

## Using Postgres (production-like)
Install Postgres and set `DATABASE_URL` in `.env`:
```
DATABASE_URL=postgres://USER:PASS@HOST:PORT/DBNAME
```
Then run migrations as above.

## Running the worker (cron)
The simple approach is to call the management command periodically from crontab or a scheduler like systemd/cron, e.g. to run every 5 minutes:
```
*/5 * * * * /full/path/to/.venv/bin/python /path/to/project/manage.py sync_holdings >> /var/log/portfolio_sync.log 2>&1
```
The command will iterate active portfolios and call the trigger registered for each broker type code. Triggers are pluggable and should use broker account credentials for API calls if needed.

## Adding a new trigger
1. Create a new file `portfolio/triggers/mybroker.py`
2. Implement a class inheriting from `BaseTrigger` and register with `@register('MYBROKER')`
3. Use `self.broker_account.credential.credentials` to read stored credentials (JSON) and make API calls.
4. The `fetch_holdings()` method must return a list of dicts with keys at minimum: `symbol`, `quantity`, `avg_price`. Extra keys can be `asset_type`, `isin`, `market_value`, `as_of`, `source_snapshot_id`, `meta`.

## Notes & next steps
- The included trigger is a mocked example. Replace it with real broker API integration and handle authentication/encryption for credentials.
- Consider adding tasks using Celery for larger-scale background processing and richer scheduling.
- Add automated tests and validation for trigger outputs.
- You may want to implement webhooks or push-based updates where brokers support it instead of polling.

---

If you want, I can:
- Add a sample Dockerfile & docker-compose with Postgres.
- Add Celery + Redis setup for background workers.
- Implement one real broker integration (if you provide API docs/credentials).

## Celery Integration (workers & scheduling)

This project includes a Celery configuration and a wrapper Celery task `portfolio.tasks.sync_holdings_task`
which calls the existing `sync_holdings` management command. We use Redis as the broker/result backend.

### Environment variables (recommended in `.env`)
```
# Redis/Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Django
DATABASE_URL=sqlite:///db.sqlite3
SECRET_KEY=dev-secret-key
DEBUG=True
```
If Redis is running on your system (you mentioned you have it), default settings will connect to `redis://localhost:6379/0`.

### Run locally (development)
1. Activate your virtualenv and install requirements:
   ```bash
   pip install -r requirements.txt
   ```
2. Apply migrations and create a superuser:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```
3. Start Django dev server (in one terminal):
   ```bash
   python manage.py runserver
   ```
4. Start a Celery worker (in another terminal):
   ```bash
   celery -A portfolio_project worker --loglevel=info
   ```
5. (Optional) Start Celery Beat to run periodic tasks (in another terminal):
   ```bash
   celery -A portfolio_project beat --loglevel=info
   ```

Now the `sync_holdings_task` will be executed by Celery Beat according to the schedule (every 5 minutes by default). You can also trigger the task manually from Django shell:
```bash
python manage.py shell
>>> from portfolio.tasks import sync_holdings_task
>>> sync_holdings_task.delay()
```

### Run as systemd services (production-like)
See `systemd/README.md` for example unit files. Replace placeholders:
- `<USER>` — linux user that will run the services
- `<PROJECT_PATH>` — full path to the project directory (where manage.py is)
- `<VENV_PATH>` — full path to your virtualenv

Enable and start services after placing them under `/etc/systemd/system/`:
```bash
sudo systemctl daemon-reload
sudo systemctl enable portfolio_celery.service
sudo systemctl enable portfolio_celery_beat.service
sudo systemctl start portfolio_celery.service
sudo systemctl start portfolio_celery_beat.service
sudo journalctl -u portfolio_celery -f
```

### Cron alternative
If you prefer cron over Celery Beat, you can add a crontab entry to run the management command every N minutes (see `systemd/cron_example.sh`).

---

If you want, I can also:
- Add a `docker-compose.yml` that brings up Postgres, Redis, Django, Celery worker & beat so you can run everything with `docker compose up`.
- Harden credential storage (encrypt broker credentials in DB).
- Add monitoring/log rotation / stdout handling for systemd units.
