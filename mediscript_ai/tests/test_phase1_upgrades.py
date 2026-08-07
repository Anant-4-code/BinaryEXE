import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.security import create_access_token, decode_token_payload
from app.models.models import User, AuditLog
from app.services.deid_service import DeidService
from app.services.audit_service import log_audit_event
from app.services.storage_service import LocalStorageService


@pytest.fixture
def db_session(tmp_path):
    db_file = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_deid_service_scrubbing():
    raw_text = "Patient Rahul Sharma (phone +91 9876543210, email rahul@gmail.com) presents with distal radius fracture."
    scrubbed = DeidService.scrub_text(raw_text)
    assert "+91 9876543210" not in scrubbed
    assert "rahul@gmail.com" not in scrubbed
    assert "[PHONE_REDACTED]" in scrubbed or "[EMAIL_REDACTED]" in scrubbed


def test_deid_payload_preparation():
    patient_info = {
        "name": "Dr. Priya Mehta",
        "phone": "9998887776",
        "email": "priya@sanjeevani.ai",
        "disease_or_condition": "Right ankle fracture"
    }
    clinical_info = {"findings": "Displaced fracture in calcaneus for patient Dr. Priya Mehta"}
    
    payload, reid_map = DeidService.prepare_deidentified_payload(patient_info, clinical_info)
    assert "ANON-PATIENT-" in payload["patient"]["patient_code"]
    assert "Dr. Priya Mehta" not in payload["patient"]["patient_code"]
    assert reid_map["real_name"] == "Dr. Priya Mehta"


def test_audit_logging(db_session):
    user = User(email="testdoc@sanjeevani.ai", role="doctor", hashed_password="pw")
    db_session.add(user)
    db_session.commit()

    entry = log_audit_event(
        db_session,
        actor_user=user,
        action="VIEW_XRAY",
        resource_type="scan",
        resource_id="101",
        details={"status": "reviewed"}
    )
    db_session.commit()

    saved_log = db_session.query(AuditLog).filter(AuditLog.id == entry.id).first()
    assert saved_log is not None
    assert saved_log.actor_role == "doctor"
    assert saved_log.action == "VIEW_XRAY"


def test_storage_service(tmp_path):
    storage = LocalStorageService(base_dir=tmp_path)
    import io
    content = b"fake xray binary content"
    file_obj = io.BytesIO(content)

    key = storage.save_file(file_obj, "test_xray.png", folder="scans")
    assert key == "scans/test_xray.png"
    assert (tmp_path / "scans" / "test_xray.png").exists()

    url = storage.get_file_path_or_url(key)
    assert "/uploads/scans/test_xray.png" in url


def test_jwt_roles():
    token = create_access_token(subject="doctor@sanjeevani.ai", role="doctor", user_id=42)
    payload = decode_token_payload(token)
    assert payload["sub"] == "doctor@sanjeevani.ai"
    assert payload["role"] == "doctor"
    assert payload["user_id"] == 42
