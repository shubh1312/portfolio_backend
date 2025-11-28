import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_project.settings')

app = Celery('portfolio_project')
# read config from Django settings, CELERY_ prefixed keys
app.config_from_object('django.conf:settings', namespace='CELERY')
# autodiscover tasks in installed apps
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
