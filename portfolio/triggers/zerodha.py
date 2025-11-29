# portfolio/triggers/zerodha.py
from .registry import register
from .base import BaseTrigger
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict

from kiteconnect import KiteConnect
import redis

from portfolio.debug_helpers import wait_for_debugger
from django.conf import settings

logger = logging.getLogger(__name__)


@register("zerodha")
class ZerodhaTrigger(BaseTrigger):
    """
    Trigger for Zerodha (Kite).

    Reads EVERYTHING from Redis under:
        broker:<broker_id>:kite

    Redis value example:
        {
          "api_key": "xxxx",
          "api_secret": "yyyy",
          "access_token": "zzzz",
          "expires_at": "2025-11-30T10:49:34.058973+00:00"
        }

    DB is only backup for api_key / api_secret.
    """

    def __init__(self, broker_account):
        super().__init__(broker_account)

        # DB fallback credentials (optional now)
        try:
            self.creds = broker_account.credential.credentials or {}
        except Exception:
            self.creds = {}

        self.broker_account = broker_account

        redis_url = getattr(settings, "REDIS_URL", "redis://127.0.0.1:6379/0")
        self._redis = redis.from_url(redis_url, decode_responses=True)

        # UPDATED KEY
        self._redis_key = f"broker:{self.broker_account.id}:kite"

    # -------------------------------------------------------------
    # Redis helper
    # -------------------------------------------------------------
    def _get_access_info_from_redis(self) -> Optional[Dict]:
        """
        Reads the Redis entry which contains:
            api_key, api_secret, access_token, expires_at
        """

        raw = self._redis.get(self._redis_key)
        if not raw:
            logger.error("Redis key %s not found.", self._redis_key)
            return None

        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                logger.error("Redis payload is not a dict: %s", raw)
                return None

            # Validate access_token
            if "access_token" not in payload:
                logger.error("Redis entry missing access_token: %s", raw)
                return None

            return payload

        except Exception as e:
            logger.exception("Invalid JSON in Redis key %s: %s", self._redis_key, e)
            return None

    def _redis_token_is_valid(self, payload: Dict) -> bool:
        """Check expires_at if present."""
        expires_at = payload.get("expires_at")
        if not expires_at:
            return True

        try:
            dt = datetime.fromisoformat(expires_at)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt > datetime.now(timezone.utc)
        except Exception:
            logger.warning("Cannot parse expires_at=%s; treating token as valid", expires_at)
            return True

    # -------------------------------------------------------------
    # Token resolver
    # -------------------------------------------------------------
    def get_access_token(self) -> Dict:
        """
        Always read access token from Redis.
        If invalid/missing, instruct admin to regenerate.
        """

        payload = self._get_access_info_from_redis()
        if not payload:
            raise RuntimeError(
                f"Redis entry '{self._redis_key}' missing or invalid.\n"
                f"Expected JSON like:\n{json.dumps({'api_key':'...', 'api_secret':'...', 'access_token':'...', 'expires_at':'...'}, indent=2)}"
            )

        if not self._redis_token_is_valid(payload):
            raise RuntimeError(
                f"Access token under Redis key '{self._redis_key}' is expired.\n"
                f"Please run: python manage.py kite_generate_token --broker-id {self.broker_account.id}"
            )

        return {
            "access_token": payload.get("access_token"),
            "api_key": payload.get("api_key") or self.creds.get("api_key"),
            "api_secret": payload.get("api_secret") or self.creds.get("api_secret"),
            "expires_at": payload.get("expires_at"),
            "source": "redis",
        }

    # -------------------------------------------------------------
    # Holdings fetch
    # -------------------------------------------------------------
    def fetch_holdings(self):

        try:
            token_info = self.get_access_token()
        except Exception as e:
            logger.exception("Access token error: %s", e)
            return {"status": "error", "error": str(e)}

        access_token = token_info["access_token"]
        api_key = token_info["api_key"]

        if not api_key:
            return {"status": "error", "error": "api_key missing in Redis or DB."}

        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)

        try:
            holdings_raw = kite.holdings()
            positions_raw = kite.positions()
            try:
                margins_equity = kite.margins("equity")
            except Exception:
                margins_equity = None

            output = []
            now = datetime.now(timezone.utc)

            for item in holdings_raw:
                output.append({
                    "symbol": item.get("tradingsymbol"),
                    "quantity": float(item.get("quantity", 0)),
                    "avg_price": float(item.get("average_price", 0)),
                    "asset_type": item.get("product") or "stock",
                    "isin": item.get("isin"),
                    "market_value": float(item.get("last_price", 0)) * float(item.get("quantity", 0)),
                    "as_of": now,
                    "source_snapshot_id": item.get("instrument_token"),
                    "meta": item,
                })

            return {
                "status": "ok",
                "data": output,
                "raw": {
                    "holdings": holdings_raw,
                    "positions": positions_raw,
                    "margins_equity": margins_equity
                },
                "token_source": token_info.get("source")
            }

        except Exception as e:
            logger.exception("Error calling Kite holdings: %s", e)
            return {"status": "error", "error": str(e)}
