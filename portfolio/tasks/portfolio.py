# portfolio/tasks/portfolio.py
from celery import shared_task, group
from django.apps import apps
from .broker import broker_action_task

@shared_task(bind=True)
def portfolio_sync_task(self, portfolio_id, actions=None):
    Portfolio = apps.get_model('portfolio', 'Portfolio')
    try:
        p = Portfolio.objects.get(id=portfolio_id)
    except Portfolio.DoesNotExist:
        return {'status': 'not_found', 'portfolio_id': portfolio_id}

    actions = actions or ['holdings']  # default actions

    sigs = []
    for acc in p.broker_accounts.select_related('broker_type').all():
        for action in actions:
            sigs.append(broker_action_task.s(portfolio_id, acc.id, action))

    if not sigs:
        return {'status': 'no_brokers'}

    # parallel execution of broker tasks
    job = group(sigs).apply_async()
    return {'group_id': job.id, 'tasks': len(sigs)}
