from app.tasks.celery_app import celery_app
from app.services.notification_service import send_push


@celery_app.task
def send_push_notification(fcm_token: str, title: str, body: str, data: dict | None = None):
    send_push(fcm_token=fcm_token, title=title, body=body, data=data)
