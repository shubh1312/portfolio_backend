# portfolio/management/commands/kite_generate_token.py

import webbrowser
import json
from datetime import datetime, timedelta, timezone

from django.core.management.base import BaseCommand
from django.conf import settings

from kiteconnect import KiteConnect
import redis

from portfolio.models import BrokerAccount


class Command(BaseCommand):
    help = "Manually generate Zerodha access_token and store EVERYTHING in Redis (api_key, api_secret, access_token)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--broker-id",
            type=int,
            required=True,
            help="BrokerAccount ID to generate access token for."
        )

    def handle(self, *args, **options):
        broker_id = options["broker_id"]

        # ----------------------------------------------------------------------
        # 1. Load creds from DB (api_key and api_secret ONLY)
        # ----------------------------------------------------------------------
        try:
            broker = BrokerAccount.objects.select_related("credential").get(id=broker_id)
        except BrokerAccount.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"BrokerAccount {broker_id} not found."))
            return

        creds = broker.credential.credentials or {}
        api_key = creds.get("api_key")
        api_secret = creds.get("api_secret")

        if not api_key or not api_secret:
            self.stderr.write(self.style.ERROR(
                'DB credentials must contain only:\n{"api_key": "...", "api_secret": "..."}'
            ))
            return

        # ----------------------------------------------------------------------
        # 2. Generate login URL and open browser
        # ----------------------------------------------------------------------
        kite = KiteConnect(api_key=api_key)
        login_url = kite.login_url()

        self.stdout.write(self.style.MIGRATE_HEADING("\nSTEP 1: Log in to Kite\n"))
        self.stdout.write(self.style.SUCCESS("Open this URL in your browser:"))
        self.stdout.write(self.style.HTTP_INFO(f"{login_url}\n"))

        try:
            webbrowser.open(login_url)
        except Exception:
            pass

        # ----------------------------------------------------------------------
        # 3. User pastes request_token
        # ----------------------------------------------------------------------
        self.stdout.write(self.style.MIGRATE_HEADING(
            "STEP 2: After login, copy 'request_token' from redirect URL\n"
        ))
        request_token = input("Paste request_token here: ").strip()

        if not request_token:
            self.stderr.write(self.style.ERROR("No request_token provided."))
            return

        # ----------------------------------------------------------------------
        # 4. Exchange request_token → access_token
        # ----------------------------------------------------------------------
        self.stdout.write(self.style.MIGRATE_HEADING("\nSTEP 3: Exchanging token...\n"))

        try:
            session_data = kite.generate_session(request_token, api_secret=api_secret)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Token exchange failed: {e}"))
            return

        access_token = session_data.get("access_token")
        if not access_token:
            self.stderr.write(self.style.ERROR("No access_token returned by Kite"))
            return

        expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()

        # ----------------------------------------------------------------------
        # 5. Save EVERYTHING to Redis under a single key
        # ----------------------------------------------------------------------
        redis_url = getattr(settings, "REDIS_URL", "redis://127.0.0.1:6379/0")
        r = redis.from_url(redis_url, decode_responses=True)

        redis_key = f"broker:{broker_id}:kite"

        store_data = {
            "api_key": api_key,
            "api_secret": api_secret,
            "access_token": access_token,
            "expires_at": expires_at,
        }

        # Save with TTL = 24 hours
        r.set(redis_key, json.dumps(store_data), ex=24 * 3600)

        # ----------------------------------------------------------------------
        # 6. Print success
        # ----------------------------------------------------------------------
        self.stdout.write(self.style.SUCCESS("\nSUCCESS! Access token stored in Redis.\n"))
        self.stdout.write(self.style.HTTP_INFO(f"Redis Key: {redis_key}\n"))
        self.stdout.write(self.style.HTTP_INFO(json.dumps(store_data, indent=2)))
        self.stdout.write(self.style.SUCCESS("\nYour trigger can now read from Redis directly.\n"))
