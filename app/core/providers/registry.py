from app.core.providers.base import CollectionProvider, DisbursementProvider
from app.core.providers.flutterwave import FlutterwaveProvider
from app.core.providers.lianlian import LianLianProvider
from app.core.config import settings

# Registry maps the provider name stored in the corridors table to a live instance.
# To add a new provider: implement the interface, instantiate here, add to the dict.

COLLECTION_PROVIDERS: dict[str, CollectionProvider] = {
    "flutterwave": FlutterwaveProvider(
        api_key=settings.FLUTTERWAVE_SECRET_KEY,
        base_url=settings.FLUTTERWAVE_BASE_URL,
    ),
    # "mpesa": MpesaProvider(
    #     consumer_key=settings.MPESA_CONSUMER_KEY,
    #     consumer_secret=settings.MPESA_CONSUMER_SECRET,
    # ),
}

DISBURSEMENT_PROVIDERS: dict[str, DisbursementProvider] = {
    "lianlian": LianLianProvider(
        app_id=settings.LIANLIAN_APP_ID,
        merchant_id=settings.LIANLIAN_MERCHANT_ID,
        api_key=settings.LIANLIAN_API_KEY,
        base_url=settings.LIANLIAN_BASE_URL,
    ),
    # "airwallex": AirwallexProvider(
    #     client_id=settings.AIRWALLEX_CLIENT_ID,
    #     api_key=settings.AIRWALLEX_API_KEY,
    # ),
}


def get_collection_provider(name: str) -> CollectionProvider:
    provider = COLLECTION_PROVIDERS.get(name)
    if not provider:
        raise ValueError(f"Collection provider '{name}' is not registered")
    return provider


def get_disbursement_provider(name: str) -> DisbursementProvider:
    provider = DISBURSEMENT_PROVIDERS.get(name)
    if not provider:
        raise ValueError(f"Disbursement provider '{name}' is not registered")
    return provider
