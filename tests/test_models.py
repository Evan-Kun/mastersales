import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.db import Base
from database.models import Company, Contact, Meeting, NurtureSequence, NurtureEnrollment, Proposal


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_create_company(db_session):
    company = Company(
        company_name="Steel Corp",
        company_industry="Steel Fabrication",
        company_location="Perth, WA",
    )
    db_session.add(company)
    db_session.commit()
    assert company.id is not None
    assert company.company_name == "Steel Corp"


def test_create_contact_with_company(db_session):
    company = Company(company_name="Steel Corp", company_industry="Steel")
    db_session.add(company)
    db_session.commit()

    contact = Contact(
        first_name="John",
        last_name="Smith",
        job_title="Operations Manager",
        lead_status="New",
        company_id=company.id,
    )
    db_session.add(contact)
    db_session.commit()
    assert contact.id is not None
    assert contact.company.company_name == "Steel Corp"


def test_create_meeting(db_session):
    company = Company(company_name="Test Co", company_industry="Mining")
    db_session.add(company)
    db_session.commit()
    contact = Contact(first_name="Jane", last_name="Doe", company_id=company.id, lead_status="New")
    db_session.add(contact)
    db_session.commit()

    meeting = Meeting(
        contact_id=contact.id,
        title="Intro Call",
        meeting_time=datetime(2026, 3, 1, 10, 0),
        duration_minutes=30,
        status="Scheduled",
    )
    db_session.add(meeting)
    db_session.commit()
    assert meeting.id is not None
    assert meeting.contact.first_name == "Jane"


def test_create_proposal(db_session):
    company = Company(company_name="Fab Ltd", company_industry="Fabrication")
    db_session.add(company)
    db_session.commit()
    contact = Contact(first_name="Bob", last_name="Jones", company_id=company.id, lead_status="Qualified")
    db_session.add(contact)
    db_session.commit()

    proposal = Proposal(
        contact_id=contact.id,
        products=[{"name": "CorrShield Base Coat", "qty": 100}],
        pricing=4500.00,
        status="Draft",
    )
    db_session.add(proposal)
    db_session.commit()
    assert proposal.id is not None
    assert proposal.products[0]["name"] == "CorrShield Base Coat"


def test_nurture_enrollment(db_session):
    seq = NurtureSequence(
        name="Steel Fabricator Intro",
        description="Intro sequence for steel fabricators",
        steps=[
            {"day_offset": 0, "subject": "Welcome", "body_template": "Hi {first_name}..."},
            {"day_offset": 3, "subject": "Follow up", "body_template": "Just checking in..."},
        ],
    )
    db_session.add(seq)
    db_session.commit()

    company = Company(company_name="NZ Steel", company_industry="Steel")
    db_session.add(company)
    db_session.commit()
    contact = Contact(first_name="Tim", last_name="Lee", company_id=company.id, lead_status="New")
    db_session.add(contact)
    db_session.commit()

    enrollment = NurtureEnrollment(
        contact_id=contact.id,
        sequence_id=seq.id,
        current_step=0,
        status="Active",
    )
    db_session.add(enrollment)
    db_session.commit()
    assert enrollment.sequence.name == "Steel Fabricator Intro"
    assert len(enrollment.sequence.steps) == 2
