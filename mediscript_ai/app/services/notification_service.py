import logging
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.models import NotificationPreference, User, Notification

logger = logging.getLogger("sanjeevani.notifications")


def find_upcoming_notifications(db: Session) -> List[Notification]:
    """Finds notifications scheduled in the upcoming window."""
    now = datetime.utcnow()
    window = now + timedelta(minutes=60)
    return db.query(Notification).filter(
        Notification.scheduled_for >= now,
        Notification.scheduled_for <= window,
        Notification.sent == False
    ).all()


class NotificationService:
    """
    Multi-channel notification dispatcher (In-App, SMS, WhatsApp, Voice Call).
    Dispatches patient medication reminders, report alerts, and refill status updates.
    """

    @classmethod
    def get_patient_channel_preference(cls, db: Session, user_id: int) -> Tuple[str, str]:
        pref = db.query(NotificationPreference).filter(NotificationPreference.user_id == user_id).first()
        if not pref:
            return "in_app", "en"
        return pref.channel, pref.language


    @classmethod
    def send_notification(
        cls,
        db: Session,
        user: User,
        title: str,
        message: str,
        category: str = "medication_reminder"
    ) -> Dict[str, Any]:
        channel, language = cls.get_patient_channel_preference(db, user.id)

        dispatch_record = {
            "user_id": user.id,
            "recipient": user.phone or user.email,
            "channel": channel,
            "language": language,
            "title": title,
            "message": message,
            "status": "sent"
        }

        if channel == "whatsapp":
            cls._send_whatsapp(dispatch_record)
        elif channel == "sms":
            cls._send_sms(dispatch_record)
        elif channel == "voice_call":
            cls._send_voice(dispatch_record)
        else:
            cls._send_in_app(dispatch_record)

        return dispatch_record

    @classmethod
    def _send_whatsapp(cls, record: Dict[str, Any]):
        logger.info(f"[WHATSAPP DISPATCH] To {record['recipient']} ({record['language']}): {record['title']} - {record['message']}")

    @classmethod
    def _send_sms(cls, record: Dict[str, Any]):
        logger.info(f"[SMS DISPATCH] To {record['recipient']}: {record['title']} - {record['message']}")

    @classmethod
    def _send_voice(cls, record: Dict[str, Any]):
        logger.info(f"[VOICE CALL DISPATCH] Calling {record['recipient']}: Playing TTS ({record['language']}) - {record['message']}")

    @classmethod
    def _send_in_app(cls, record: Dict[str, Any]):
        logger.info(f"[IN-APP DISPATCH] User {record['user_id']}: {record['title']} - {record['message']}")
