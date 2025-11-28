# portfolio/tasks/broker.py
from celery import shared_task
from django.apps import apps
from portfolio.triggers import registry
from portfolio.services import persist_holdings   # <-- important

ACTION_HANDLERS = {
    'holdings': 'fetch_holdings',
}

@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def broker_action_task(self, portfolio_id, broker_account_id, action):
    BrokerAccount = apps.get_model('portfolio', 'BrokerAccount')
    try:
        acc = BrokerAccount.objects.select_related('broker_type', 'credential').get(id=broker_account_id)
    except BrokerAccount.DoesNotExist as exc:
        raise self.retry(exc=exc, countdown=60)
    
    trigger_cls = registry.get_trigger_for_code(acc.broker_type.code)
    if not trigger_cls:
        return {'status': 'no_trigger'}

    trigger = trigger_cls(acc)

    # Pick correct function: fetch_holdings etc.
    method_name = ACTION_HANDLERS[action]
    data = getattr(trigger, method_name)()

    # 🚀 instead of updating DB here:
    saved = persist_holdings(acc, data)

    return {'status': 'ok', 'saved': saved}
