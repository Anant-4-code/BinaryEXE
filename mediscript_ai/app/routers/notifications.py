from typing import Any, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Notification, Prescription, User
from app.schemas.schemas import NotificationOut
from app.services.notification_service import find_upcoming_notifications
from app.core.deps import get_current_user


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", response_model=List[NotificationOut])
def list_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    notifs = (
        db.query(Notification)
        .join(Prescription)
        .filter(Prescription.user_id == current_user.id)
        .order_by(Notification.scheduled_for.desc())
        .limit(100)
        .all()
    )
    return notifs


@router.post("/poll", response_model=List[NotificationOut])
def poll_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    find_upcoming_notifications(db)
    notifs = (
        db.query(Notification)
        .join(Prescription)
        .filter(Prescription.user_id == current_user.id)
        .order_by(Notification.scheduled_for.desc())
        .limit(100)
        .all()
    )
    return notifs
