# portfolio/triggers/coinswitch.py

import logging
from typing import Dict, Any, Optional

import requests
from cryptography.hazmat.primitives.asymmetric import ed25519
from django.utils import timezone

from .registry import register
from .base import BaseTrigger

logger = logging.getLogger(__name__)

BASE_URL = "https://coinswitch.co"


@register("coinswitch")
class CoinSwitchTrigger(BaseTrigger):
    """
    Trigger for CoinSwitch PRO.

    Credentials are read directly from broker_account.credential.credentials:

        {
          "api_key": "YOUR_API_KEY",
          "secret_key_hex": "HEX_ENCODED_ED25519_PRIVATE_KEY"
        }

    No Redis / access_token handling needed.
    """

    def __init__(self, broker_account):
        super().__init__(broker_account)

        try:
            self.creds = broker_account.credential.credentials or {}
        except Exception:
            self.creds = {}

        self.broker_account = broker_account

        self.api_key: Optional[str] = self.creds.get("api_key")
        # allow both keys, pick whichever you store
        self.secret_key_hex: Optional[str] = (
            self.creds.get("secret_key_hex") or self.creds.get("secret_key")
        )

    # -------------------------------------------------------------
    # Low-level API helpers
    # -------------------------------------------------------------
    def _get_server_time(self) -> int:
        """
        GET /trade/api/v2/time
        Returns serverTime (epoch ms).
        """
        url = f"{BASE_URL}/trade/api/v2/time"
        resp = requests.get(url, headers={"Content-Type": "application/json"}, json={})
        resp.raise_for_status()
        data = resp.json()
        return int(data["serverTime"])

    def _generate_signature(self, method: str, endpoint: str, epoch_ms: str) -> str:
        """
        Generate Ed25519 signature as per CoinSwitch docs:
            signature_msg = method + endpoint + epoch_ms
        """
        if not self.secret_key_hex:
            raise RuntimeError("secret_key_hex missing in broker credentials")

        signature_msg = method + endpoint + epoch_ms
        request_bytes = signature_msg.encode("utf-8")

        secret_key_bytes = bytes.fromhex(self.secret_key_hex)
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(secret_key_bytes)
        signature_bytes = private_key.sign(request_bytes)
        return signature_bytes.hex()

    def _get_portfolio_raw(self) -> Dict[str, Any]:
        """
        Call GET /trade/api/v2/user/portfolio and return parsed JSON.
        """
        if not self.api_key:
            raise RuntimeError("api_key missing in broker credentials")

        method = "GET"
        endpoint = "/trade/api/v2/user/portfolio"

        server_time_ms = self._get_server_time()
        epoch_ms = str(server_time_ms)
        signature = self._generate_signature(method, endpoint, epoch_ms)

        url = f"{BASE_URL}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "X-AUTH-APIKEY": self.api_key,
            "X-AUTH-SIGNATURE": signature,
            "X-AUTH-EPOCH": epoch_ms,
        }

        resp = requests.get(url, headers=headers, json={})
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------
    # Holdings fetch (normalized to same shape as Zerodha trigger)
    # -------------------------------------------------------------
    def fetch_holdings(self):
        """
        Fetch holdings from CoinSwitch and normalize to the generic
        holdings format expected by persist_holdings.

        Output structure:
        {
          "status": "ok",
          "data": [ { ...normalized holding... }, ... ],
          "raw": { "holdings": <raw_api_data_list> },
          "token_source": "broker_credentials"
        }
        """
        try:
            portfolio_raw = self._get_portfolio_raw()
        except Exception as e:
            logger.exception("Error calling CoinSwitch portfolio: %s", e)
            return {"status": "error", "error": str(e)}

        # Your example shape: { "data": [ { ... }, ... ] }
        holdings_raw = portfolio_raw.get("data") or portfolio_raw.get("portfolio") or []
        if not isinstance(holdings_raw, list):
            logger.error("Unexpected CoinSwitch portfolio format: %r", portfolio_raw)
            return {
                "status": "error",
                "error": "Unexpected CoinSwitch portfolio format.",
                "raw": {"holdings": portfolio_raw},
            }

        now = timezone.now()
        output = []

        for item in holdings_raw:
            try:
                currency = item.get("currency")
                # Ignore INR summary row completely
                if not currency or currency == "INR":
                    continue

                # ---- Quantity ----
                # Use main_balance as the quantity (can be "0" string).
                quantity = float(item.get("main_balance") or 0.0)

                # ---- Average price ----
                # buy_average_price is given as string in INR.
                avg_price = float(item.get("buy_average_price") or 0.0)

                # ---- Last price ----
                # Prefer sell_rate, then buy_rate, else infer from current_value / quantity.
                last_price_raw = item.get("sell_rate") or item.get("buy_rate")
                if last_price_raw is None and quantity:
                    current_value = item.get("current_value")
                    if current_value is not None:
                        try:
                            last_price_raw = float(current_value) / float(quantity or 1)
                        except Exception:
                            last_price_raw = 0.0
                last_price = float(last_price_raw or 0.0)

                # Crypto has no real "close_price" from this API, keep None.
                close_price = None

                output.append({
                    # --- Stock fields (for Stock model) ---
                    "symbol": currency,        # e.g. "BTC", "ETH", "SHIB"
                    "isin": None,             # crypto has no ISIN
                    "asset_type": "crypto",   # distinguish from equity, mf, etc.
                    "last_price": last_price,
                    "close_price": close_price,

                    # Price snapshot timestamp
                    "price_as_of": now,

                    # --- Holding fields (for Holding model) ---
                    "quantity": quantity,
                    "avg_price": avg_price,
                    "currency": "INR",        # all values are INR
                    "as_of": now,
                    "source_snapshot_id": currency,  # stable identifier
                    "meta": item,             # keep full raw for debugging
                })
            except Exception:
                logger.exception("Error normalizing CoinSwitch holding item: %r", item)
                continue

        return {
            "status": "ok",
            "data": output,
            "raw": {
                "holdings": holdings_raw,
            },
            "token_source": "broker_credentials",
        }
