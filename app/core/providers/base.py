from abc import ABC, abstractmethod
from decimal import Decimal


class CollectionProvider(ABC):
    """
    Abstract interface for all local-currency collection providers.
    Every integration (Flutterwave, M-Pesa, etc.) must implement this.
    The payment service calls this interface — never a concrete provider directly.
    """

    @abstractmethod
    async def initiate_payment(
        self,
        amount: Decimal,
        currency: str,
        user_id: str,
        transaction_ref: str,
        payment_method: str,    # bank_transfer | card | ussd | mobile_money
        metadata: dict,
    ) -> dict:
        """
        Initiate a payment collection.
        Returns: { reference, payment_instructions, expires_at }
        payment_instructions contains what the mobile app shows the user
        (virtual account number, card form URL, USSD string, etc.)
        """

    @abstractmethod
    async def verify_payment(
        self,
        provider_reference: str,
        transaction_ref: str,
    ) -> dict:
        """
        Verify a payment's status by querying the provider.
        Returns: { status: "successful"|"failed"|"pending", amount, currency }
        """

    @abstractmethod
    async def initiate_refund(
        self,
        provider_reference: str,
        amount: Decimal,
        reason: str,
    ) -> dict:
        """
        Initiate a refund for a failed or disputed transaction.
        Returns: { refund_reference, status }
        """

    @abstractmethod
    async def get_fx_rate(
        self,
        source_currency: str,
        target_currency: str,
    ) -> Decimal:
        """
        Fetch the live mid-market FX rate for a currency pair.
        Returns CNY per NGN (e.g. 0.005204 for NGN→CNY).
        """


class DisbursementProvider(ABC):
    """
    Abstract interface for all target-currency disbursement providers.
    Every integration (LianLian, Airwallex, etc.) must implement this.
    """

    @abstractmethod
    async def pay_qr(
        self,
        qr_code: str,
        amount: Decimal,
        currency: str,
        transaction_ref: str,
        metadata: dict,
    ) -> dict:
        """
        Submit a payment to a QR code recipient.
        Returns: { disbursement_reference, status }
        """

    @abstractmethod
    async def check_status(
        self,
        disbursement_reference: str,
    ) -> dict:
        """
        Check the current status of a disbursement.
        Returns: { status: "processing"|"completed"|"failed", ... }
        """

    @abstractmethod
    async def supported_payment_types(self) -> list[str]:
        """
        Return the list of supported target types.
        e.g. ["alipay_qr", "wechat_qr"]
        """
