import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.providers.base import CollectionProvider
from app.core.config import settings


class FlutterwaveProvider(CollectionProvider):

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self._headers = {"Authorization": f"Bearer {api_key}"}

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def initiate_payment(
        self, amount: Decimal, currency: str, user_id: str,
        transaction_ref: str, payment_method: str, metadata: dict,
    ) -> dict:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=20)

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{self.base_url}/virtual-account-numbers",
                json={
                    "email": metadata.get("email", ""),
                    "is_permanent": False,
                    "tx_ref": transaction_ref,
                    "amount": float(amount),
                    "narration": f"Curensi {transaction_ref}",
                    "frequency": 1,
                    "duration": 20,
                },
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()["data"]

        return {
            "reference": transaction_ref,
            "payment_instructions": {
                "type": "virtual_account",
                "account_number": data["account_number"],
                "bank_name": data["bank_name"],
                "account_name": data["account_name"],
                "amount": float(amount),
                "currency": currency,
                "expires_at": expires_at.isoformat(),
            },
            "expires_at": expires_at.isoformat(),
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def verify_payment(self, provider_reference: str, transaction_ref: str) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{self.base_url}/transactions/{provider_reference}/verify",
                headers=self._headers,
            )
            if resp.status_code != 200:
                return {"status": "failed", "amount": Decimal("0"), "currency": "NGN"}
            data = resp.json()["data"]

        return {
            "status": "successful" if data["status"] == "successful" else "failed",
            "amount": Decimal(str(data["amount"])),
            "currency": data["currency"],
            "flw_ref": data.get("flw_ref"),
        }

    async def initiate_refund(self, provider_reference: str, amount: Decimal, reason: str) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{self.base_url}/transactions/{provider_reference}/refund",
                json={"amount": float(amount), "comments": reason},
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()["data"]

        return {
            "refund_reference": str(data.get("id", "")),
            "status": data.get("status", "pending"),
        }

    async def get_fx_rate(self, source_currency: str, target_currency: str) -> Decimal:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{self.base_url}/transfers/rates",
                params={"source_currency": source_currency, "destination_currency": target_currency, "amount": "1"},
                headers=self._headers,
            )
            resp.raise_for_status()
            return Decimal(str(resp.json()["data"]["rate"]))

    @staticmethod
    def verify_webhook(payload: bytes, signature: str) -> bool:
        return hmac.compare_digest(signature, settings.FLUTTERWAVE_WEBHOOK_SECRET)
