# portfolio/services.py

from portfolio.models import Holding
from django.utils import timezone
from django.db import transaction


# portfolio/services.py

from decimal import Decimal
from django.utils import timezone
from django.db import transaction

from portfolio.models import Holding, Stock


def persist_holdings(broker_account, holdings_data):
    """
    Persist holdings snapshot for a broker_account.

    - Upserts Stock rows (symbol/isin/asset_type + latest price data)
    - Upserts Holding rows (per broker_account + stock)

    Input can be:
      - dict with 'data' key (trigger output), or
      - plain list of holding dicts.
    """
    # Normalize input
    if isinstance(holdings_data, dict):
        holdings_list = holdings_data.get("data", [])
    else:
        holdings_list = holdings_data or []

    saved = 0
    now = timezone.now()

    with transaction.atomic():
        for item in holdings_list:
            if not isinstance(item, dict):
                continue

            symbol = item.get("symbol")
            if not symbol:
                # If there's no symbol, we can't do much
                continue

            isin = item.get("isin")
            asset_type = item.get("asset_type") or "equity"

            # --- 1) Upsert Stock -----------------------------------------
            stock_as_of = item.get("price_as_of") or item.get("as_of") or now

            last_price_raw = item.get("last_price")
            close_price_raw = item.get("close_price")

            # Safely convert to Decimal or None
            last_price = (
                Decimal(str(last_price_raw))
                if last_price_raw is not None
                else Decimal("0")
            )
            close_price = (
                Decimal(str(close_price_raw))
                if close_price_raw is not None
                else None
            )

            stock, _ = Stock.objects.update_or_create(
                symbol=symbol,
                isin=isin,
                asset_type=asset_type,
                defaults={
                    "as_of": stock_as_of,
                    "last_price": last_price,
                    "close_price": close_price,
                    "received_at": now,
                },
            )

            # --- 2) Upsert Holding ---------------------------------------
            holding_as_of = item.get("as_of") or now

            quantity_raw = item.get("quantity", 0)
            avg_price_raw = item.get("avg_price", 0)

            quantity = Decimal(str(quantity_raw or 0))
            avg_price = Decimal(str(avg_price_raw or 0))

            holding_defaults = {
                "quantity": quantity,
                "avg_price": avg_price,
                "currency": item.get("currency", "INR"),
                "as_of": holding_as_of,
                "source_snapshot_id": item.get("source_snapshot_id"),
                "meta": item.get("meta"),
            }

            # One holding row per (broker_account, stock)
            Holding.objects.update_or_create(
                broker_account=broker_account,
                stock=stock,
                defaults=holding_defaults,
            )

            saved += 1

    return saved

