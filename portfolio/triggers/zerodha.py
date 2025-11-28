# portfolio/triggers/zerodha.py
from .registry import register
from .base import BaseTrigger
import requests
import datetime

@register("zerodha")
class ZerodhaTrigger(BaseTrigger):

    def __init__(self, broker_account):
        super().__init__(broker_account)
        self.creds = broker_account.credential.credentials
        # Example credentials:
        # { "access_token": "...", "client_id": "123456" }

    def fetch_holdings(self):
        """
        Make actual API call to Zerodha to fetch holdings.
        Must return list[ dict(...) ] in a standard format.
        """

        # headers = {
        #     "Authorization": f"Bearer {self.creds.get('access_token')}",
        #     "X-Client-Id": self.creds.get('client_id'),
        #     "Content-Type": "application/json",
        # }

        # url = "https://api.kite.trade/portfolio/holdings"
        # response = requests.get(url, headers=headers, timeout=10)
        # response.raise_for_status()

        # raw_data = response.json()["data"]    # Example API structure

        # # Convert API response to your internal format:
        # output = []
        # now = datetime.datetime.now(datetime.timezone.utc)

        # for item in raw_data:
        #     output.append({
        #         "symbol": item["tradingsymbol"],
        #         "quantity": float(item["quantity"]),
        #         "avg_price": float(item["average_price"]),
        #         "asset_type": "stock",
        #         "isin": item.get("isin"),
        #         "market_value": float(item.get("last_price", 0)) * float(item["quantity"]),
        #         "as_of": now,
        #         "source_snapshot_id": item.get("instrument_token"),
        #         "meta": item,  # FULL raw API object saved for debugging
        #     })

        return {"status": "not_implemented"}

    def fetch_transactions(self):
        """
        Example for transaction data sync
        """
        url = "https://api.kite.trade/portfolio/transactions"
        headers = {"Authorization": f"Bearer {self.creds.get('access_token')}"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        raw_data = response.json()["data"]

        output = []
        now = datetime.datetime.now(datetime.timezone.utc)

        for t in raw_data:
            output.append({
                "symbol": t["tradingsymbol"],
                "quantity": float(t["quantity"]),
                "price": float(t["price"]),
                "trade_type": t["transaction_type"],
                "trade_time": t["order_timestamp"],
                "meta": t,
            })

        return output
