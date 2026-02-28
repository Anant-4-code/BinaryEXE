from datetime import date, time, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.models import Dose, Medicine, Prescription


def generate_schedule_for_prescription(
    db: Session,
    prescription: Prescription,
    start_date: Optional[date] = None,
) -> List[Dose]:
    doses: List[Dose] = []
    day0 = start_date or date.today()

    durations = [m.duration_days for m in (prescription.medicines or []) if m.duration_days and m.duration_days > 0]
    default_duration = max(durations) if durations else 7

    for med in prescription.medicines:
        assert isinstance(med, Medicine)
        duration_days = med.duration_days if (med.duration_days and med.duration_days > 0) else default_duration

        # PRN / As-needed medicines do not generate fixed schedule
        if med.frequency and med.frequency.lower().strip() in {"prn", "sos", "as needed", "if necessary"}:
            continue

        per_day = 0
        if med.frequency:
            freq = med.frequency.lower().strip()
            # Support both abbreviations and people-friendly strings
            freq_map = {
                "od": 1, "once daily": 1,
                "bd": 2, "bid": 2, "twice daily": 2,
                "tds": 3, "tid": 3, "three times daily": 3,
                "qid": 4, "four times daily": 4,
                "q4h": 6, "every 4 hours": 6,
                "q6h": 4, "every 6 hours": 4,
                "hs": 1, "at bedtime": 1,
            }
            per_day = freq_map.get(freq, 0)

        if per_day <= 0:
            per_day = 3

        times: List[time] = []
        if per_day == 1:
            times = [time(8, 0)]
        elif per_day == 2:
            times = [time(8, 0), time(20, 0)]
        elif per_day == 3:
            times = [time(8, 0), time(14, 0), time(20, 0)]
        elif per_day == 4:
            times = [time(6, 0), time(12, 0), time(18, 0), time(22, 0)]
        else:
            # Generic fallback for uncommon frequencies (e.g. q4h -> 6/day)
            # Spread doses across the day starting at 08:00.
            if per_day <= 0:
                per_day = 3
            start_hour = 8
            step_hours = max(1, int(round(24 / float(per_day))))
            hours = []
            h = start_hour
            for _ in range(per_day):
                hours.append(h % 24)
                h += step_hours
            # Ensure uniqueness and stable ordering
            hours = sorted(set(hours))
            times = [time(int(h), 0) for h in hours]

        for day_offset in range(duration_days):
            dose_date = day0 + timedelta(days=day_offset)
            for t in times:
                dose = Dose(
                    prescription_id=prescription.id,
                    medicine_id=med.id,
                    date=dose_date,
                    time=t,
                    taken=False,
                )
                db.add(dose)
                doses.append(dose)

    db.commit()
    db.refresh(prescription)
    return doses

