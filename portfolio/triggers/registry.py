"""Simple registry to map broker codes to trigger classes."""
REGISTRY = {}

def register(code):
    def _inner(cls):
        REGISTRY[code] = cls
        return cls
    return _inner

def get_trigger_for_code(code):
    return REGISTRY.get(code)
