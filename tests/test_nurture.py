import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from database.db import Base
from database.models import Company, Contact, NurtureSequence, NurtureEnrollment
from pipeline.nurture_engine import enroll_contact, get_current_step_content, advance_step


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        company = Company(company_name="Steel Co", company_industry="Steel")
        session.add(company)
        session.flush()
        contact = Contact(first_name="Jane", last_name="Doe", company_id=company.id, lead_status="New")
        session.add(contact)
        seq = NurtureSequence(
            name="Test Sequence",
            steps=[
                {"day_offset": 0, "subject": "Step 1", "body_template": "Hi {first_name} at {company_name}"},
                {"day_offset": 3, "subject": "Step 2", "body_template": "Follow up {first_name}"},
            ],
        )
        session.add(seq)
        session.commit()
        yield session


def test_enroll_contact(db_session):
    contact = db_session.query(Contact).first()
    seq = db_session.query(NurtureSequence).first()
    enrollment = enroll_contact(db_session, contact.id, seq.id)
    assert enrollment.current_step == 0
    assert enrollment.status == "Active"


def test_get_current_step_content(db_session):
    contact = db_session.query(Contact).first()
    seq = db_session.query(NurtureSequence).first()
    enrollment = enroll_contact(db_session, contact.id, seq.id)
    content = get_current_step_content(db_session, enrollment.id)
    assert content["subject"] == "Step 1"
    assert "Jane" in content["body"]
    assert "Steel Co" in content["body"]


def test_advance_step(db_session):
    contact = db_session.query(Contact).first()
    seq = db_session.query(NurtureSequence).first()
    enrollment = enroll_contact(db_session, contact.id, seq.id)
    advance_step(db_session, enrollment.id)
    db_session.refresh(enrollment)
    assert enrollment.current_step == 1

    advance_step(db_session, enrollment.id)
    db_session.refresh(enrollment)
    assert enrollment.status == "Completed"
