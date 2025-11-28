from .registry import register
from .base import BaseTrigger
import datetime

@register('ZERODHA')
class ZerodhaTrigger(BaseTrigger):
    def fetch_holdings(self):
        # This is a sample/mock implementation. Replace with real API calls.
        # Use self.broker_account and self.broker_account.credential.credentials for auth.
        now = datetime.datetime.now(datetime.timezone.utc)
        return [
            {
                'symbol': 'TCS',
                'quantity': 10,
                'avg_price': 2200.0,
                'asset_type': 'stock',
                'isin': None,
                'market_value': 22000.0,
                'as_of': now,
                'source_snapshot_id': 'mock-1',
                'meta': {'note': 'mocked holding'},
            }
        ]
