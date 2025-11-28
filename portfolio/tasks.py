from celery import shared_task
from django.core.management import call_command
from django.utils import timezone

@shared_task(bind=True)
def sync_holdings_task(self):
    """Celery task wrapper around the management command to sync holdings."""
    # You can also directly import the logic instead of calling a management command.
    call_command('sync_holdings')
    return {'status': 'completed', 'time': str(timezone.now())}
