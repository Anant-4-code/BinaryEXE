from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Dose, Medicine


router = APIRouter(prefix="/calendar", tags=["calendar"])


def _parse_hhmm_list(times_csv: str) -> List[time]:
    out: List[time] = []
    for raw in (times_csv or "").split(","):
        t = raw.strip()
        if not t:
            continue
        parts = t.split(":")
        if len(parts) != 2:
            raise ValueError("Invalid time format")
        hh = int(parts[0])
        mm = int(parts[1])
        if hh < 0 or hh > 23 or mm < 0 or mm > 59:
            raise ValueError("Invalid time value")
        out.append(time(hh, mm))
    # sort + unique
    out = sorted({t for t in out}, key=lambda x: (x.hour, x.minute))
    return out


def _scheduled_dt(d: Dose) -> Optional[datetime]:
    if not getattr(d, "date", None) or not getattr(d, "time", None):
        return None
    try:
        return datetime.combine(d.date, d.time)
    except Exception:
        return None


def _dose_is_missed(d: Dose, now: datetime) -> bool:
    if d.taken:
        return False
    sdt = _scheduled_dt(d)
    return bool(sdt and sdt < now)


def _dose_is_late(d: Dose) -> bool:
    if not d.taken or not d.taken_at:
        return False
    sdt = _scheduled_dt(d)
    return bool(sdt and d.taken_at and d.taken_at > sdt)


@router.post("/doses/{dose_id}/toggle")
def toggle_dose_taken(dose_id: int, db: Session = Depends(get_db)) -> Any:
    dose = db.query(Dose).filter(Dose.id == dose_id).first()
    if not dose:
        raise HTTPException(status_code=404, detail="Dose not found")

    # Real-time restriction: user can mark taken only on the scheduled day.
    # (Prevents backdating/forward-dating adherence data.)
    today = datetime.now().date()
    if dose.date and dose.date != today:
        raise HTTPException(status_code=400, detail="You can only mark a dose as taken on its scheduled day")

    # Time window restriction: allow marking taken starting 1 hour before scheduled time.
    # Applies only when switching from pending -> taken.
    now = datetime.now()
    if not dose.taken:
        sdt = _scheduled_dt(dose)
        if sdt:
            earliest = sdt - timedelta(hours=1)
            if now < earliest:
                raise HTTPException(
                    status_code=400,
                    detail="You can mark this dose as taken only within 1 hour before its scheduled time",
                )

    dose.taken = not dose.taken
    dose.taken_at = now if dose.taken else None
    db.commit()

    return {
        "id": dose.id,
        "taken": dose.taken,
        "taken_at": dose.taken_at.isoformat() if dose.taken_at else None,
        "missed": _dose_is_missed(dose, now),
        "late": _dose_is_late(dose),
    }


@router.get("/prescriptions/{prescription_id}/month")
def get_month_summary(
    prescription_id: int,
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)

    rows = (
        db.query(Dose, Medicine)
        .join(Medicine, Medicine.id == Dose.medicine_id)
        .filter(Dose.prescription_id == prescription_id)
        .filter(Dose.date >= start)
        .filter(Dose.date < end)
        .all()
    )

    by_day: Dict[str, Dict[str, int]] = {}
    by_day_med: Dict[str, Dict[int, Dict[str, Any]]] = {}
    now = datetime.now()
    for d, m in rows:
        key = d.date.isoformat()
        if key not in by_day:
            by_day[key] = {"total": 0, "taken": 0, "missed": 0}
        by_day[key]["total"] += 1
        if d.taken:
            by_day[key]["taken"] += 1
        elif _dose_is_missed(d, now):
            by_day[key]["missed"] += 1

        if key not in by_day_med:
            by_day_med[key] = {}
        if m.id not in by_day_med[key]:
            by_day_med[key][m.id] = {
                "medicine_id": m.id,
                "medicine_name": m.normalized_name or m.original_name,
                "total": 0,
                "taken": 0,
                "missed": 0,
            }
        by_day_med[key][m.id]["total"] += 1
        if d.taken:
            by_day_med[key][m.id]["taken"] += 1
        elif _dose_is_missed(d, now):
            by_day_med[key][m.id]["missed"] += 1

    def _status_for_counts(total: int, taken: int, missed: int, day_date: date) -> str:
        if day_date > now.date():
            return "future"
        if total > 0 and taken == total:
            return "complete"
        if taken > 0:
            return "partial"
        if missed > 0:
            return "missed"
        return "missed"

    # Determine color status per day (combined across all medicines)
    days: Dict[str, Dict[str, Any]] = {}
    for day, counts in by_day.items():
        total = counts["total"]
        taken = counts["taken"]
        missed = counts["missed"]
        day_date = date.fromisoformat(day)

        status = _status_for_counts(total, taken, missed, day_date)

        meds_out: List[Dict[str, Any]] = []
        for med_id, mc in (by_day_med.get(day) or {}).items():
            mt = int(mc.get("total") or 0)
            mk = int(mc.get("taken") or 0)
            mm = int(mc.get("missed") or 0)
            meds_out.append(
                {
                    "medicine_id": med_id,
                    "medicine_name": mc.get("medicine_name") or "",
                    "total": mt,
                    "taken": mk,
                    "missed": mm,
                    "status": _status_for_counts(mt, mk, mm, day_date),
                }
            )
        meds_out.sort(key=lambda x: (x.get("medicine_name") or "").lower())

        days[day] = {
            "total": total,
            "taken": taken,
            "missed": missed,
            "status": status,
            "completion_percentage": (taken / total * 100.0) if total else 0.0,
            "medicines": meds_out,
        }

    return {"year": year, "month": month, "days": days}


@router.get("/prescriptions/{prescription_id}/day")
def get_day_details(
    prescription_id: int,
    day: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        day_date = date.fromisoformat(day)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid day format. Use YYYY-MM-DD")

    doses = (
        db.query(Dose, Medicine)
        .join(Medicine, Medicine.id == Dose.medicine_id)
        .filter(Dose.prescription_id == prescription_id)
        .filter(Dose.date == day_date)
        .order_by(Dose.time.asc())
        .all()
    )

    now = datetime.now()
    items = []
    for d, m in doses:
        sdt = _scheduled_dt(d)
        items.append(
            {
                "dose_id": d.id,
                "medicine_id": m.id,
                "medicine_name": m.normalized_name or m.original_name,
                "frequency": (m.frequency or ""),
                "duration_days": (m.duration_days or 0),
                "time": d.time.strftime("%H:%M") if d.time else "",
                "taken": bool(d.taken),
                "taken_at": d.taken_at.isoformat() if d.taken_at else None,
                "missed": _dose_is_missed(d, now),
                "late": _dose_is_late(d),
                "scheduled_at": sdt.isoformat() if sdt else None,
            }
        )

    return {"day": day_date.isoformat(), "items": items}


@router.get("/prescriptions/{prescription_id}/analytics")
def get_analytics_series(
    prescription_id: int,
    days: int = Query(30, ge=7, le=365),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    end_day = datetime.now().date()
    start_day = end_day - timedelta(days=days - 1)

    rows = (
        db.query(
            Dose.date.label("day"),
            func.count(Dose.id).label("total"),
            func.sum(case((Dose.taken.is_(True), 1), else_=0)).label("taken"),
        )
        .filter(Dose.prescription_id == prescription_id)
        .filter(Dose.date >= start_day)
        .filter(Dose.date <= end_day)
        .group_by(Dose.date)
        .order_by(Dose.date.asc())
        .all()
    )

    by_day: Dict[date, Dict[str, int]] = {}
    for r in rows:
        d = r.day
        total = int(r.total or 0)
        taken = int(r.taken or 0)
        by_day[d] = {"total": total, "taken": taken}

    series: List[Dict[str, Any]] = []
    cur = start_day
    while cur <= end_day:
        c = by_day.get(cur) or {"total": 0, "taken": 0}
        total = int(c.get("total") or 0)
        taken = int(c.get("taken") or 0)
        missed = total - taken
        pct = (taken / total * 100.0) if total else 0.0
        series.append(
            {
                "day": cur.isoformat(),
                "total": total,
                "taken": taken,
                "missed": missed,
                "percentage": pct,
            }
        )
        cur = cur.fromordinal(cur.toordinal() + 1)

    totals = {
        "total": sum(x["total"] for x in series),
        "taken": sum(x["taken"] for x in series),
        "missed": sum(x["missed"] for x in series),
    }
    totals["percentage"] = (totals["taken"] / totals["total"] * 100.0) if totals["total"] else 0.0

    return {
        "prescription_id": prescription_id,
        "start_day": start_day.isoformat(),
        "end_day": end_day.isoformat(),
        "series": series,
        "totals": totals,
    }


@router.post("/medicines/{medicine_id}/reschedule")
def reschedule_medicine_times(
    medicine_id: int,
    times: str = Query(..., description="Comma separated HH:MM list"),
    start_day: Optional[str] = Query(None, description="YYYY-MM-DD (defaults to today)"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    medicine = db.query(Medicine).filter(Medicine.id == medicine_id).first()
    if not medicine:
        raise HTTPException(status_code=404, detail="Medicine not found")

    try:
        new_times = _parse_hhmm_list(times)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid times. Use HH:MM,HH:MM")
    if not new_times:
        raise HTTPException(status_code=400, detail="Please provide at least one time")

    today = datetime.now().date()
    if start_day:
        try:
            start_date = date.fromisoformat(start_day)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_day. Use YYYY-MM-DD")
    else:
        start_date = today

    # Find the next scheduled day for this medicine (to infer expected doses-per-day)
    next_dose = (
        db.query(Dose)
        .filter(Dose.medicine_id == medicine_id)
        .filter(Dose.date >= start_date)
        .order_by(Dose.date.asc())
        .first()
    )
    if not next_dose:
        raise HTTPException(status_code=400, detail="No upcoming doses to reschedule")

    expected_count = (
        db.query(Dose)
        .filter(Dose.medicine_id == medicine_id)
        .filter(Dose.date == next_dose.date)
        .count()
    )
    if expected_count != len(new_times):
        raise HTTPException(
            status_code=400,
            detail=f"This medicine has {expected_count} dose(s) per day. Provide exactly {expected_count} time(s).",
        )

    # Update remaining schedule entries and preserve history.
    # Important: even if some doses of a day are already taken, we still want to
    # reschedule the untaken ones for that day (and future days).
    doses_from_start: List[Dose] = (
        db.query(Dose)
        .filter(Dose.medicine_id == medicine_id)
        .filter(Dose.date >= start_date)
        .order_by(Dose.date.asc(), Dose.time.asc())
        .all()
    )

    updated = 0
    current_day: Optional[date] = None
    day_bucket: List[Dose] = []

    def flush_bucket():
        nonlocal updated
        if not day_bucket:
            return

        # We only apply the mapping when the day's dose count matches the expected schedule.
        if len(day_bucket) != len(new_times):
            return

        day_bucket.sort(key=lambda d: (d.time.hour, d.time.minute) if d.time else (0, 0))
        for i, d in enumerate(day_bucket):
            # Preserve taken history; reschedule only untaken doses.
            if not d.taken:
                d.time = new_times[i]
                updated += 1

    for d in doses_from_start:
        if current_day is None:
            current_day = d.date
        if d.date != current_day:
            flush_bucket()
            day_bucket = []
            current_day = d.date
        day_bucket.append(d)
    flush_bucket()

    db.commit()
    return {
        "medicine_id": medicine_id,
        "updated": updated,
        "times": [t.strftime("%H:%M") for t in new_times],
        "start_day": start_date.isoformat(),
    }

