# portfolio/tasks/__init__.py
# Import submodules so Celery autodiscover registers tasks.
from . import dispatcher
# import other modules if present/expected
from . import portfolio
from . import broker
