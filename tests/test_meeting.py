import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from database.db import Base
from database.models import Company, Contact, Meeting
from scheduler.meeting import create_meeting, get_upcoming_meetings


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        company = Company(company_name="Test Co", company_industry="Steel")
        session.add(company)
        session.flush()
        contact = Contact(first_name="John", last_name="Doe", company_id=company.id, lead_status="New")
        session.add(contact)
        session.commit()
        yield session


def test_create_meeting(db_session):
    contact = db_session.query(Contact).first()
    meeting = create_meeting(
        db_session,
        contact_id=contact.id,
        title="Intro Call",
        meeting_time=datetime.now() + timedelta(days=1),
        duration_minutes=30,
    )
    assert meeting.id is not None
    assert meeting.title == "Intro Call"


def test_get_upcoming_meetings(db_session):
    contact = db_session.query(Contact).first()
    create_meeting(db_session, contact.id, "Past", datetime.now() - timedelta(days=1), 30)
    create_meeting(db_session, contact.id, "Future", datetime.now() + timedelta(days=1), 30)
    upcoming = get_upcoming_meetings(db_session)
    assert len(upcoming) == 1
    assert upcoming[0].title == "Future"
