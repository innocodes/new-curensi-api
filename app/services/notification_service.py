import json
import firebase_admin
from firebase_admin import credentials, messaging
from app.core.config import settings

_app_initialized = False


def _init_firebase():
    global _app_initialized
    if not _app_initialized and not firebase_admin._apps:
        try:
            key_data = json.loads(settings.FIREBASE_SERVICE_ACCOUNT_KEY)
            if key_data:
                cred = credentials.Certificate(key_data)
                firebase_admin.initialize_app(cred)
                _app_initialized = True
        except Exception:
            pass  # FCM optional — app runs fine without it


def send_push(fcm_token: str, title: str, body: str, data: dict | None = None) -> bool:
    """
    Send a Firebase Cloud Messaging push notification.
    Returns True on success, False if FCM is not configured or send fails.
    """
    _init_firebase()
    if not _app_initialized or not fcm_token:
        return False

    try:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
            token=fcm_token,
        )
        messaging.send(message)
        return True
    except Exception:
        return False
