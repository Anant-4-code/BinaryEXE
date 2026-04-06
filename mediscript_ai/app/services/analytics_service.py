from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import Dose
from app.schemas.schemas import AnalyticsSummary


def compute_analytics_for_prescription(db: Session, prescription_id: int) -> AnalyticsSummary:
    total_doses = db.query(func.count(Dose.id)).filter(Dose.prescription_id == prescription_id).scalar() or 0
    taken_doses = (
        db.query(func.count(Dose.id))
        .filter(Dose.prescription_id == prescription_id, Dose.taken.is_(True))
        .scalar()
        or 0
    )

    adherence_percentage = (taken_doses / total_doses * 100.0) if total_doses > 0 else 0.0

    missed_doses = total_doses - taken_doses

    today = date.today()
    current_streak = 0

    day = today
    while True:
        day_doses = db.query(Dose).filter(Dose.prescription_id == prescription_id, Dose.date == day).all()
        if not day_doses:
            break
        if all(d.taken for d in day_doses):
            current_streak += 1
            day = day.fromordinal(day.toordinal() - 1)
        else:
            break

    return AnalyticsSummary(
        total_doses=total_doses,
        taken_doses=taken_doses,
        adherence_percentage=adherence_percentage,
        missed_doses=missed_doses,
        current_streak=current_streak,
    )

