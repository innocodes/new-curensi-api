from decimal import Decimal
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.providers.base import DisbursementProvider
from app.core.config import settings


class LianLianProvider(DisbursementProvider):
    """
    LianLian Global disbursement provider.

    Production requests require RSA-SHA256 signing of each payload.
    The _sign() stub below is where that goes once sandbox credentials arrive.
    All other orchestration is wired — only the signing and exact endpoint
    paths need updating against LianLian's API spec.
    """

    def __init__(self, app_id: str, merchant_id: str, api_key: str, base_url: str):
        self.app_id = app_id
        self.merchant_id = merchant_id
        self.api_key = api_key
        self.base_url = base_url

    def _sign(self, payload: dict) -> dict:
        # TODO: sign with LIANLIAN_PRIVATE_KEY (RSA-SHA256) per LianLian API spec
        return payload

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=5, max=30))
    async def pay_qr(
        self, qr_code: str, amount: Decimal, currency: str,
        transaction_ref: str, metadata: dict,
    ) -> dict:
        payload = self._sign({
            "app_id": self.app_id,
            "merchant_id": self.merchant_id,
            "order_id": transaction_ref,
            "trans_currency": currency,
            "trans_amount": str(amount),
            "payment_method": "ALIPAY_QR",
            "payee_info": {"qr_code": qr_code},
            "memo": metadata.get("memo", "Curensi payment"),
        })

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self.base_url}/api/payment/disburse",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        return {
            "disbursement_reference": data.get("transaction_no", transaction_ref),
            "status": data.get("status", "processing"),
        }

    async def check_status(self, disbursement_reference: str) -> dict:
        payload = self._sign({
            "app_id": self.app_id,
            "transaction_no": disbursement_reference,
        })

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{self.base_url}/api/payment/query",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        status_map = {
            "SUCCESS": "completed",
            "PROCESSING": "processing",
            "FAILED": "failed",
        }
        return {
            "status": status_map.get(data.get("status", ""), "processing"),
            "alipay_ref": data.get("alipay_trade_no"),
        }

    async def supported_payment_types(self) -> list[str]:
        return ["alipay_qr", "wechat_qr"]

    @staticmethod
    def verify_webhook(payload: bytes, signature: str) -> bool:
        # TODO: verify RSA signature using LIANLIAN_PUBLIC_KEY
        return True
