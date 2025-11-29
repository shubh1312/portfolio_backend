# portfolio/services.py

from portfolio.models import Holding
from django.utils import timezone
from django.db import transaction


def persist_holdings(broker_account, holdings_data):
    """
    Actual DB update logic for holdings.
    Called by broker worker OR management command OR API.

    Accepts either:
      - a plain list of holding dicts, OR
      - a dict with a 'data' key containing that list
        (for backward compatibility with older trigger outputs).
    """
    # Normalize input to a list of dicts
    if isinstance(holdings_data, dict):
        holdings_list = holdings_data.get("data", [])
    else:
        holdings_list = holdings_data or []

    saved = 0
    with transaction.atomic():
        for item in holdings_list:
            # Safety: skip anything that isn't a dict
            if not isinstance(item, dict):
                continue

            obj, created = Holding.objects.update_or_create(
                broker_account=broker_account,
                symbol=item["symbol"],
                as_of=item.get("as_of", timezone.now()),
                defaults={
                    "asset_type": item.get("asset_type", "stock"),
                    "isin": item.get("isin"),
                    "quantity": item.get("quantity", 0),
                    "avg_price": item.get("avg_price", 0),
                    "currency": item.get("currency", "INR"),
                    "cost_value": item.get("cost_value"),
                    "market_value": item.get("market_value"),
                    "meta": item.get("meta"),
                },
            )
            saved += 1
    return saved
