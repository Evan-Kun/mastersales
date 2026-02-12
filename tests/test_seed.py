import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.db import Base
from database.models import Company, Contact, NurtureSequence
from database.seed import seed_demo_data


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_seed_creates_companies(db_session):
    seed_demo_data(db_session)
    companies = db_session.query(Company).all()
    assert len(companies) >= 5


def test_seed_creates_contacts_linked_to_companies(db_session):
    seed_demo_data(db_session)
    contacts = db_session.query(Contact).all()
    assert len(contacts) >= 10
    for contact in contacts:
        assert contact.company_id is not None


def test_seed_creates_nurture_sequences(db_session):
    seed_demo_data(db_session)
    sequences = db_session.query(NurtureSequence).all()
    assert len(sequences) >= 2
    for seq in sequences:
        assert len(seq.steps) >= 2


def test_seed_is_idempotent(db_session):
    seed_demo_data(db_session)
    count1 = db_session.query(Company).count()
    seed_demo_data(db_session)
    count2 = db_session.query(Company).count()
    assert count1 == count2
