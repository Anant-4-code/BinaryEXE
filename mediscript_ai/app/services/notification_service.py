from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session

from app.models.models import Dose, Notification, NotificationTypeEnum


def find_upcoming_notifications(db: Session, window_minutes: int = 10) -> List[Notification]:
    now = datetime.utcnow()
    window_end = now + timedelta(minutes=window_minutes)

    doses = (
        db.query(Dose)
        .filter(Dose.taken.is_(False))
        .filter(Dose.date >= now.date())
        .all()
    )

    notifications: List[Notification] = []
    for dose in doses:
        scheduled_dt = datetime.combine(dose.date, dose.time)
        if now <= scheduled_dt <= window_end:
            notif = Notification(
                prescription_id=dose.prescription_id,
                dose_id=dose.id,
                type=NotificationTypeEnum.UPCOMING,
                message=f"Dose for medicine {dose.medicine_id} at {dose.time.strftime('%H:%M')}",
                scheduled_for=scheduled_dt,
            )
            db.add(notif)
            notifications.append(notif)

    db.commit()
    return notifications

