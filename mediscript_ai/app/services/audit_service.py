import json
from datetime import datetime
from typing import Optional, Any, Dict
from sqlalchemy.orm import Session
from app.models.models import AuditLog, User


def log_audit_event(
    db: Session,
    actor_user: Optional[User],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """
    Record an immutable audit log entry for HIPAA and DPDP compliance.
    Must be called within the same active database transaction or flushed immediately.
    """
    actor_id = actor_user.id if actor_user else None
    actor_role = actor_user.role if actor_user else "anonymous"

    audit_entry = AuditLog(
        actor_user_id=actor_id,
        actor_role=actor_role,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        ip_address=ip_address,
        details_json=json.dumps(details) if details else None,
        occurred_at=datetime.utcnow(),
    )
    db.add(audit_entry)
    db.flush()
    return audit_entry
