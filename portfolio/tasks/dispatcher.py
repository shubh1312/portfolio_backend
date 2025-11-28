# portfolio/tasks/dispatcher.py
from celery import shared_task
from django.apps import apps
from portfolio.tasks.portfolio import portfolio_sync_task

@shared_task(bind=True)
def active_users_data_sync_worker(self):
    User = apps.get_model('portfolio', 'User')
    Portfolio = apps.get_model('portfolio', 'Portfolio')

    active_users = User.objects.filter(active=True).values_list('id', flat=True)
    total = 0
    for uid in active_users:
        pids = Portfolio.objects.filter(user_id=uid, active=True).values_list('id', flat=True)
        for pid in pids:
            # enqueue portfolio-level task
            portfolio_sync_task.delay(pid)
            total += 1
    return {'enqueued_portfolios': total}
