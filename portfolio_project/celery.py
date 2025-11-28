import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_project.settings')

app = Celery('portfolio_project')
# read config from Django settings, CELERY_ prefixed keys
app.config_from_object('django.conf:settings', namespace='CELERY')

# ensure workers send events and sent status to the broker (required by Flower)
app.conf.update(
    task_send_sent_event=True,
    worker_send_task_events=True,
    # optional: if you want a default result_expires (seconds)
    result_expires=3600,
)

# autodiscover tasks in installed apps
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
