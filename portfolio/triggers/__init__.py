# from .registry import registry
# portfolio/triggers/__init__.py
from . import registry   # expose the registry module as portfolio.triggers.registry
from . import zerodha  # ensure ZerodhaTrigger is registered