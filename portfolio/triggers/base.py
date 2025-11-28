from abc import ABC, abstractmethod

class BaseTrigger(ABC):
    def __init__(self, broker_account):
        self.broker_account = broker_account

    @abstractmethod
    def fetch_holdings(self):
        """Return a list of holding dicts. Each dict must have at minimum: symbol, quantity, avg_price."""
        raise NotImplementedError
