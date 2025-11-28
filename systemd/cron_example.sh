# Example crontab entry to run the management command every 5 minutes (alternative to Celery Beat)
# Edit with: crontab -e (as the user that owns the project files)
# CRON:
*/5 * * * * /path/to/venv/bin/python /path/to/project/manage.py sync_holdings >> /path/to/project/logs/sync_holdings.log 2>&1
