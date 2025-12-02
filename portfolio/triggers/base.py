from abc import ABC, abstractmethod

class BaseTrigger(ABC):
    def __init__(self, broker_account):
        self.broker_account = broker_account

    @abstractmethod
    def fetch_holdings(self):
        raise NotImplementedError
