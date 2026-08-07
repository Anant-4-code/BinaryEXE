import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.main import app
from app.models.models import User, Prescription, NotificationPreference, RefillRequest, AuditLog
from app.core.security import create_access_token


@pytest.fixture
def test_setup(tmp_path):
    db_file = tmp_path / "patient_test.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()

    # Seed patient and doctor
    patient = User(
        email="patient_test@sanjeevani.ai",
        name="Rohan Verma",
        role="patient",
        hashed_password="pw",
        is_active=True
    )
    doctor = User(
        email="doc_test@sanjeevani.ai",
        name="Dr. Mehta",
        role="doctor",
        hashed_password="pw",
        is_active=True
    )
    session.add(patient)
    session.add(doctor)
    session.commit()

    prescription = Prescription(
        user_id=patient.id,
        title="Amoxicillin 500mg",
        status="active",
        created_at=datetime.utcnow()
    )
    session.add(prescription)
    session.commit()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    token = create_access_token(subject=patient.email, role="patient", user_id=patient.id)
    client = TestClient(app)
    client.headers = {"Authorization": f"Bearer {token}"}

    yield client, session, patient, prescription

    app.dependency_overrides.clear()
    session.close()


def test_access_log_endpoint(test_setup):
    client, session, patient, prescription = test_setup

    # Seed an audit log entry
    audit = AuditLog(
        actor_user_id=patient.id,
        actor_role="doctor",
        action="VIEW_REPORT",
        resource_type="prescription",
        resource_id=str(prescription.id),
        occurred_at=datetime.utcnow()
    )
    session.add(audit)
    session.commit()

    response = client.get("/patient/access-log")
    assert response.status_code == 200
    data = response.json()
    assert "access_log" in data
    assert len(data["access_log"]) >= 1
    assert data["access_log"][0]["action"] == "VIEW_REPORT"


def test_health_timeline_endpoint(test_setup):
    client, session, patient, prescription = test_setup

    response = client.get("/patient/timeline")
    assert response.status_code == 200
    data = response.json()
    assert "timeline" in data
    assert len(data["timeline"]) >= 1
    assert data["timeline"][0]["type"] == "prescription"


def test_refill_request_endpoint(test_setup):
    client, session, patient, prescription = test_setup

    response = client.post(f"/patient/prescriptions/{prescription.id}/refill-request")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    # Verify database entry
    refill = session.query(RefillRequest).filter(RefillRequest.prescription_id == prescription.id).first()
    assert refill is not None
    assert refill.status == "requested"


def test_notification_preferences_endpoint(test_setup):
    client, session, patient, prescription = test_setup

    response = client.put(
        "/patient/settings/notifications",
        data={"channel": "whatsapp", "language": "hi"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["channel"] == "whatsapp"
    assert data["language"] == "hi"

    pref = session.query(NotificationPreference).filter(NotificationPreference.user_id == patient.id).first()
    assert pref is not None
    assert pref.channel == "whatsapp"
    assert pref.language == "hi"
