import json
import logging
import firebase_admin
from firebase_admin import credentials, messaging
from app.core.config import settings

logger = logging.getLogger(__name__)
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


async def send_push_to_user(
    user_id: str,
    title: str,
    body: str,
    data: dict | None = None,
    db=None,
) -> bool:
    """
    Look up the user's FCM token from the DB and send a push notification.
    Used by Celery tasks that have a DB session but not the token directly.
    """
    if db is None:
        return False
    try:
        from sqlalchemy import select
        from app.models.user import User
        result = await db.execute(select(User.fcm_token).where(User.id == user_id))
        fcm_token = result.scalar_one_or_none()
        if not fcm_token:
            return False
        return send_push(fcm_token, title, body, data)
    except Exception as e:
        logger.warning(f"send_push_to_user failed for {user_id}: {e}")
        return False
