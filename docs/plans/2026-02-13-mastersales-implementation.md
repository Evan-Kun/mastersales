# MasterSales Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local sales activation platform for Corrizon Australasia that replicates Apollo.io/Sales Navigator functionality — LinkedIn scraping, CRM, pipeline, proposals, nurturing, and scheduling.

**Architecture:** Monolithic FastAPI app with Jinja2 + HTMX frontend, SQLite database via SQLAlchemy, Playwright-based LinkedIn scraper, WeasyPrint for PDF generation. Single `python app.py` to run.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, SQLite, Jinja2, HTMX, Alpine.js, Tailwind CSS (CDN), Playwright, WeasyPrint

---

### Task 1: Project Scaffolding & Dependencies

**Files:**
- Create: `requirements.txt`
- Create: `config.py`
- Create: `database/__init__.py`
- Create: `scraper/__init__.py`
- Create: `pipeline/__init__.py`
- Create: `proposals/__init__.py`
- Create: `proposals/templates/` (directory)
- Create: `scheduler/__init__.py`
- Create: `templates/` (directory)
- Create: `static/css/style.css`
- Create: `static/js/app.js`
- Create: `static/img/` (directory)
- Create: `output/proposals/` (directory)
- Create: `tests/__init__.py`

**Step 1: Create requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.35
jinja2==3.1.4
python-multipart==0.0.12
weasyprint==62.3
playwright==1.48.0
aiofiles==24.1.0
pydantic==2.9.0
pydantic-settings==2.5.0
pytest==8.3.0
httpx==0.27.0
```

**Step 2: Create config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "MasterSales"
    database_url: str = "sqlite:///mastersales.db"
    debug: bool = True

    # Corrizon company details
    company_name: str = "Corrizon Australasia Pty Ltd"
    company_website: str = "www.corrizon.com.au"
    company_tagline: str = "High-tech steel treatment system to prevent corrosion"

    # ICP configuration
    target_countries: list[str] = ["AU", "NZ"]
    priority_states: list[str] = ["WA", "VIC"]
    industry_keywords: list[str] = [
        "steel", "corrosion", "rust", "protection", "coating",
        "zinc", "paint", "undercoat", "treatment", "maintenance",
        "salt", "mining", "engineering", "shipbuilding", "machinery",
        "fabrication", "application",
    ]
    deal_size_min: int = 500
    deal_size_max: int = 15000
    sales_cycle: str = "monthly"
    key_differentiators: list[str] = [
        "Environmentally friendly",
        "Water based",
        "Minimal VOCs",
        "Cost saving",
        "Time saving",
        "Better schedule control",
        "Easy application",
        "Reduced preparation",
        "Simple clean up",
        "Superior protection",
    ]

    # Corrizon products for proposal generation
    products: list[dict] = [
        {"name": "CorrShield Base Coat", "description": "Water-based zinc-rich primer for steel protection", "price_per_litre": 45.00},
        {"name": "CorrShield Top Coat", "description": "Environmental barrier top coat", "price_per_litre": 38.00},
        {"name": "CorrShield Complete System", "description": "Full 2-coat anti-corrosion system", "price_per_litre": 75.00},
        {"name": "Application Training", "description": "On-site application training (per day)", "price_per_litre": 1500.00},
        {"name": "Surface Assessment", "description": "Corrosion assessment and recommendation report", "price_per_litre": 800.00},
    ]

    # Scraper settings
    linkedin_email: str = ""
    linkedin_password: str = ""
    scrape_delay_min: float = 2.0
    scrape_delay_max: float = 5.0
    scrape_max_results: int = 50

    class Config:
        env_file = ".env"


settings = Settings()
```

**Step 3: Create all directory scaffolding with __init__.py files**

Create empty `__init__.py` in: `database/`, `scraper/`, `pipeline/`, `proposals/`, `scheduler/`, `tests/`
Create empty dirs: `proposals/templates/`, `templates/`, `static/css/`, `static/js/`, `static/img/`, `output/proposals/`
Create placeholder `static/css/style.css` (empty) and `static/js/app.js` (empty).

**Step 4: Create virtual environment and install dependencies**

Run: `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
Run: `playwright install chromium`

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: project scaffolding with dependencies and config"
```

---

### Task 2: Database Models & Connection

**Files:**
- Create: `database/db.py`
- Create: `database/models.py`
- Test: `tests/test_models.py`

**Step 1: Write the test**

```python
# tests/test_models.py
import pytest
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

    from datetime import datetime
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL (modules don't exist yet)

**Step 3: Create database/db.py**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, echo=settings.debug)
SessionLocal = sessionmaker(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
```

**Step 4: Create database/models.py**

```python
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, JSON, String, Text, Integer, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.db import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_name: Mapped[str] = mapped_column(String(255))
    company_website: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company_industry: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company_size: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    company_revenue: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    company_founded: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    company_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    company_linkedin_url: Mapped[Optional[str]] = mapped_column(String(500), unique=True, nullable=True)
    company_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company_keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    abn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contacts: Mapped[list["Contact"]] = relationship(back_populates="company")


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    seniority_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email_work: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_personal: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone_mobile: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    phone_work: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(500), unique=True, nullable=True)
    location_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    location_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    location_country: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    years_in_role: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    profile_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lead_status: Mapped[str] = mapped_column(String(50), default="New")
    lead_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    lead_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    assigned_to: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_contacted: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_follow_up: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deal_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("companies.id"), nullable=True)
    company: Mapped[Optional["Company"]] = relationship(back_populates="contacts")
    meetings: Mapped[list["Meeting"]] = relationship(back_populates="contact")
    proposals: Mapped[list["Proposal"]] = relationship(back_populates="contact")
    nurture_enrollments: Mapped[list["NurtureEnrollment"]] = relationship(back_populates="contact")


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))
    title: Mapped[str] = mapped_column(String(255))
    agenda: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meeting_time: Mapped[datetime] = mapped_column(DateTime)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="Scheduled")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    contact: Mapped["Contact"] = relationship(back_populates="meetings")


class NurtureSequence(Base):
    __tablename__ = "nurture_sequences"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    enrollments: Mapped[list["NurtureEnrollment"]] = relationship(back_populates="sequence")


class NurtureEnrollment(Base):
    __tablename__ = "nurture_enrollments"

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))
    sequence_id: Mapped[int] = mapped_column(ForeignKey("nurture_sequences.id"))
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(50), default="Active")

    contact: Mapped["Contact"] = relationship(back_populates="nurture_enrollments")
    sequence: Mapped["NurtureSequence"] = relationship(back_populates="enrollments")


class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))
    products: Mapped[list] = mapped_column(JSON, default=list)
    pricing: Mapped[float] = mapped_column(Float)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    email_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="Draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    contact: Mapped["Contact"] = relationship(back_populates="proposals")
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`
Expected: All 5 tests PASS

**Step 6: Commit**

```bash
git add database/ tests/
git commit -m "feat: database models for Company, Contact, Meeting, Nurture, Proposal"
```

---

### Task 3: Seed Data for Demo

**Files:**
- Create: `database/seed.py`
- Test: `tests/test_seed.py`

**Step 1: Write the test**

```python
# tests/test_seed.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.db import Base
from database.models import Company, Contact, Meeting, NurtureSequence
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_seed.py -v`
Expected: FAIL (seed module doesn't exist)

**Step 3: Create database/seed.py**

```python
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database.models import Company, Contact, NurtureSequence


def seed_demo_data(db: Session):
    """Seed the database with realistic demo data for Corrizon's ICP."""

    # Check if already seeded
    if db.query(Company).first():
        return

    companies_data = [
        {
            "company_name": "WA Steel Fabricators",
            "company_website": "wasteel.com.au",
            "company_industry": "Steel Fabrication",
            "company_size": "50-200",
            "company_revenue": "$5M-$20M",
            "company_location": "Perth, WA",
            "company_keywords": "steel,fabrication,mining,coating",
            "abn": "12345678901",
        },
        {
            "company_name": "Southern Cross Engineering",
            "company_website": "scengineering.com.au",
            "company_industry": "Engineering & Fabrication",
            "company_size": "20-50",
            "company_revenue": "$2M-$5M",
            "company_location": "Melbourne, VIC",
            "company_keywords": "engineering,steel,maintenance,protection",
            "abn": "23456789012",
        },
        {
            "company_name": "Pilbara Mining Services",
            "company_website": "pilbaramining.com.au",
            "company_industry": "Mining Services",
            "company_size": "200-500",
            "company_revenue": "$20M-$50M",
            "company_location": "Karratha, WA",
            "company_keywords": "mining,corrosion,rust,maintenance,salt",
            "abn": "34567890123",
        },
        {
            "company_name": "NZ Marine Engineering",
            "company_website": "nzmarine.co.nz",
            "company_industry": "Shipbuilding & Marine",
            "company_size": "10-20",
            "company_revenue": "$1M-$5M",
            "company_location": "Auckland, NZ",
            "company_keywords": "shipbuilding,marine,corrosion,salt,coating",
            "abn": "",
        },
        {
            "company_name": "VicSteel Constructions",
            "company_website": "vicsteel.com.au",
            "company_industry": "Steel Construction",
            "company_size": "50-200",
            "company_revenue": "$10M-$20M",
            "company_location": "Geelong, VIC",
            "company_keywords": "steel,construction,fabrication,zinc,paint",
            "abn": "56789012345",
        },
        {
            "company_name": "Outback Machinery",
            "company_website": "outbackmachinery.com.au",
            "company_industry": "Heavy Machinery",
            "company_size": "20-50",
            "company_revenue": "$2M-$10M",
            "company_location": "Kalgoorlie, WA",
            "company_keywords": "machinery,mining,rust,treatment,maintenance",
            "abn": "67890123456",
        },
        {
            "company_name": "Canterbury Steel Works",
            "company_website": "canterburysteel.co.nz",
            "company_industry": "Steel Fabrication",
            "company_size": "10-50",
            "company_revenue": "$1M-$5M",
            "company_location": "Christchurch, NZ",
            "company_keywords": "steel,fabrication,coating,undercoat",
            "abn": "",
        },
    ]

    companies = []
    for data in companies_data:
        company = Company(**data)
        db.add(company)
        companies.append(company)
    db.flush()

    contacts_data = [
        {"first_name": "Mark", "last_name": "Thompson", "job_title": "Operations Manager", "seniority_level": "Manager", "email_work": "mark.t@wasteel.com.au", "phone_work": "+61 8 9200 1234", "location_city": "Perth", "location_state": "WA", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/mark-thompson-wa", "lead_status": "New", "lead_source": "LinkedIn", "company": companies[0]},
        {"first_name": "Sarah", "last_name": "Chen", "job_title": "Procurement Director", "seniority_level": "Director", "email_work": "sarah.chen@wasteel.com.au", "phone_work": "+61 8 9200 1235", "location_city": "Perth", "location_state": "WA", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/sarah-chen-perth", "lead_status": "Contacted", "lead_source": "LinkedIn", "deal_value": 8000, "company": companies[0]},
        {"first_name": "David", "last_name": "Williams", "job_title": "General Manager", "seniority_level": "C-Suite", "email_work": "david@scengineering.com.au", "phone_mobile": "+61 412 345 678", "location_city": "Melbourne", "location_state": "VIC", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/david-williams-melb", "lead_status": "Qualified", "lead_source": "LinkedIn", "deal_value": 12000, "company": companies[1]},
        {"first_name": "Rachel", "last_name": "O'Brien", "job_title": "Site Maintenance Manager", "seniority_level": "Manager", "email_work": "rachel.obrien@pilbaramining.com.au", "phone_work": "+61 8 9100 5678", "location_city": "Karratha", "location_state": "WA", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/rachel-obrien-pilbara", "lead_status": "Proposal", "lead_source": "LinkedIn", "deal_value": 15000, "company": companies[2]},
        {"first_name": "James", "last_name": "Hartley", "job_title": "Chief Engineer", "seniority_level": "C-Suite", "email_work": "james@pilbaramining.com.au", "location_city": "Karratha", "location_state": "WA", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/james-hartley-mining", "lead_status": "Contacted", "lead_source": "LinkedIn", "company": companies[2]},
        {"first_name": "Aroha", "last_name": "Ngata", "job_title": "Workshop Manager", "seniority_level": "Manager", "email_work": "aroha@nzmarine.co.nz", "phone_work": "+64 9 300 1234", "location_city": "Auckland", "location_state": "Auckland", "location_country": "NZ", "linkedin_url": "https://linkedin.com/in/aroha-ngata-nz", "lead_status": "New", "lead_source": "LinkedIn", "company": companies[3]},
        {"first_name": "Peter", "last_name": "Rossi", "job_title": "Production Manager", "seniority_level": "Manager", "email_work": "peter.rossi@vicsteel.com.au", "phone_mobile": "+61 423 456 789", "location_city": "Geelong", "location_state": "VIC", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/peter-rossi-geelong", "lead_status": "Negotiation", "lead_source": "LinkedIn", "deal_value": 9500, "company": companies[4]},
        {"first_name": "Emma", "last_name": "Jacobs", "job_title": "Quality Assurance Lead", "seniority_level": "Manager", "email_work": "emma.j@vicsteel.com.au", "location_city": "Geelong", "location_state": "VIC", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/emma-jacobs-qa", "lead_status": "Qualified", "lead_source": "LinkedIn", "company": companies[4]},
        {"first_name": "Bruce", "last_name": "Keller", "job_title": "Owner / Director", "seniority_level": "Owner", "email_work": "bruce@outbackmachinery.com.au", "phone_mobile": "+61 400 111 222", "location_city": "Kalgoorlie", "location_state": "WA", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/bruce-keller-outback", "lead_status": "Won", "lead_source": "LinkedIn", "deal_value": 3500, "company": companies[5]},
        {"first_name": "Hemi", "last_name": "Parata", "job_title": "Fabrication Supervisor", "seniority_level": "Manager", "email_work": "hemi@canterburysteel.co.nz", "phone_work": "+64 3 400 5678", "location_city": "Christchurch", "location_state": "Canterbury", "location_country": "NZ", "linkedin_url": "https://linkedin.com/in/hemi-parata-nz", "lead_status": "New", "lead_source": "LinkedIn", "company": companies[6]},
        {"first_name": "Lisa", "last_name": "Tanaka", "job_title": "Maintenance Coordinator", "seniority_level": "Staff", "email_work": "lisa.t@pilbaramining.com.au", "location_city": "Newman", "location_state": "WA", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/lisa-tanaka-newman", "lead_status": "Contacted", "lead_source": "LinkedIn", "company": companies[2]},
        {"first_name": "Andrew", "last_name": "Clarke", "job_title": "Structural Engineer", "seniority_level": "Staff", "email_work": "andrew.c@scengineering.com.au", "location_city": "Melbourne", "location_state": "VIC", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/andrew-clarke-eng", "lead_status": "New", "lead_source": "LinkedIn", "company": companies[1]},
    ]

    for data in contacts_data:
        company = data.pop("company")
        contact = Contact(**data, company_id=company.id)
        db.add(contact)

    # Nurture sequences
    sequences = [
        NurtureSequence(
            name="Steel Fabricator Introduction",
            description="Initial outreach sequence for steel fabrication companies",
            steps=[
                {"day_offset": 0, "subject": "Protecting Your Steel Assets", "body_template": "Hi {first_name},\n\nI noticed {company_name} works with steel fabrication and wanted to share how Corrizon's water-based anti-corrosion system is helping companies like yours save time and money on steel protection.\n\nUnlike traditional coatings, our system is environmentally friendly with minimal VOCs, requires less surface preparation, and provides superior protection.\n\nWould you be open to a quick 15-minute call to see if this could benefit your operations?\n\nBest regards,\nCorrizon Team"},
                {"day_offset": 3, "subject": "Quick Question About Your Coating Process", "body_template": "Hi {first_name},\n\nI wanted to follow up on my previous message. Many of our clients in {location_state} have told us their biggest pain points are:\n\n- Time-consuming surface preparation\n- VOC compliance costs\n- Coating failures in harsh environments\n\nOur system addresses all three. Would a brief case study be helpful?\n\nBest,\nCorrizon Team"},
                {"day_offset": 7, "subject": "Case Study: 40% Cost Reduction in Steel Protection", "body_template": "Hi {first_name},\n\nI wanted to share a quick case study from a {company_industry} company similar to {company_name}.\n\nThey switched to Corrizon's system and saw:\n- 40% reduction in coating costs\n- 60% less preparation time\n- Zero VOC compliance issues\n\nI'd love to show you how this could work for your operation. Free to chat this week?\n\nCorrizon Team"},
                {"day_offset": 14, "subject": "Final Thought on Corrosion Protection", "body_template": "Hi {first_name},\n\nI appreciate your time. If corrosion protection isn't a priority right now, no worries at all.\n\nIf anything changes, you can reach us at www.corrizon.com.au. We're always happy to do a free assessment.\n\nWishing {company_name} continued success.\n\nBest,\nCorrizon Team"},
            ],
        ),
        NurtureSequence(
            name="Post-Demo Follow-Up",
            description="Follow-up sequence after product demonstration",
            steps=[
                {"day_offset": 0, "subject": "Great Meeting Today!", "body_template": "Hi {first_name},\n\nThank you for taking the time to see our anti-corrosion system in action today. As discussed, I'll prepare a customised proposal for {company_name} based on your requirements.\n\nIn the meantime, please don't hesitate to reach out with any questions.\n\nBest,\nCorrizon Team"},
                {"day_offset": 2, "subject": "Your Customised Proposal from Corrizon", "body_template": "Hi {first_name},\n\nAs promised, please find attached your customised proposal for {company_name}.\n\nThe proposal includes our recommended system based on your specific environment and usage requirements. I've highlighted the key cost savings compared to your current approach.\n\nHappy to walk through any details — just let me know a good time.\n\nBest,\nCorrizon Team"},
                {"day_offset": 5, "subject": "Any Questions on the Proposal?", "body_template": "Hi {first_name},\n\nJust checking in to see if you've had a chance to review the proposal. I'm available this week if you'd like to discuss any aspects in detail.\n\nWe can also arrange a trial application on a small section if that would help your decision.\n\nBest,\nCorrizon Team"},
            ],
        ),
    ]

    for seq in sequences:
        db.add(seq)

    db.commit()
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_seed.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add database/seed.py tests/test_seed.py
git commit -m "feat: seed data with realistic AU/NZ steel fabrication companies and contacts"
```

---

### Task 4: FastAPI App Skeleton + Base Template

**Files:**
- Create: `app.py`
- Create: `templates/base.html`
- Create: `templates/dashboard.html`
- Create: `static/css/style.css`
- Create: `static/js/app.js`

**Step 1: Create app.py**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from config import settings
from database.db import init_db, get_db, SessionLocal
from database.models import Contact, Company, Meeting, Proposal
from database.seed import seed_demo_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        seed_demo_data(db)
    finally:
        db.close()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/")
def dashboard(request: Request, db: Session = Depends(get_db)):
    total_leads = db.query(Contact).count()
    active_deals = db.query(Contact).filter(
        Contact.lead_status.in_(["Qualified", "Proposal", "Negotiation"])
    ).count()
    proposals_sent = db.query(Proposal).filter(Proposal.status != "Draft").count()
    meetings_count = db.query(Meeting).count()

    recent_leads = db.query(Contact).order_by(Contact.created_at.desc()).limit(5).all()

    pipeline_counts = {}
    for status in ["New", "Contacted", "Qualified", "Proposal", "Negotiation", "Won", "Lost"]:
        pipeline_counts[status] = db.query(Contact).filter(Contact.lead_status == status).count()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "settings": settings,
        "total_leads": total_leads,
        "active_deals": active_deals,
        "proposals_sent": proposals_sent,
        "meetings_count": meetings_count,
        "recent_leads": recent_leads,
        "pipeline_counts": pipeline_counts,
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
```

**Step 2: Create templates/base.html**

The base layout with Tailwind CSS (CDN), HTMX, Alpine.js, navigation sidebar. Full HTML template with:
- Sidebar nav: Dashboard, Lead Sourcing, Leads, Pipeline, Meetings, Nurture, Proposals
- Main content area
- Corrizon branding in header
- HTMX and Alpine.js loaded from CDN
- Tailwind CSS loaded from CDN

**Step 3: Create templates/dashboard.html**

Dashboard extending base.html with:
- 4 summary cards (Total Leads, Active Deals, Proposals Sent, Meetings)
- Mini pipeline bar chart (colored segments per status)
- Recent leads table (last 5 added)

**Step 4: Create static/css/style.css**

Custom styles for pipeline colors, card hover effects, and Corrizon brand color (#1e3a5f navy, #f39c12 amber accent).

**Step 5: Create static/js/app.js**

HTMX configuration and Alpine.js components for interactive elements.

**Step 6: Run the app to verify**

Run: `python app.py`
Open: `http://127.0.0.1:8000`
Expected: Dashboard loads with seed data stats, nav works.

**Step 7: Commit**

```bash
git add app.py templates/ static/
git commit -m "feat: FastAPI app skeleton with dashboard and base template"
```

---

### Task 5: Leads Table Page (CRM View)

**Files:**
- Modify: `app.py` (add routes)
- Create: `templates/leads.html`
- Create: `templates/lead_detail.html`
- Create: `templates/partials/lead_row.html` (HTMX partial)

**Step 1: Add leads routes to app.py**

Add routes:
- `GET /leads` — renders leads table with search/filter/sort
- `GET /leads/{id}` — renders single lead detail
- `PUT /leads/{id}` — updates lead fields (HTMX inline edit)
- `DELETE /leads/{id}` — deletes a lead
- `POST /leads/{id}/status` — changes lead status (HTMX)
- `GET /leads/search` — HTMX partial for filtered results

Query params for `/leads`: `q` (search), `status` (filter), `state` (filter), `sort` (field), `order` (asc/desc)

**Step 2: Create templates/leads.html**

Full CRM table view with:
- Search bar (HTMX live search, `hx-get="/leads/search"` `hx-trigger="keyup changed delay:300ms"`)
- Filter dropdowns: Status, State, Country
- Sortable column headers
- Table columns: Name, Company, Title, Location, Email, Status (color badge), Score, Deal Value, Last Contact
- Click row → lead detail page
- Bulk select checkboxes

**Step 3: Create templates/lead_detail.html**

Single lead profile page with:
- Contact info card (all fields)
- Company info card
- Activity timeline (meetings, proposals, nurture steps)
- Notes editor
- Quick actions: Change status, schedule meeting, create proposal, enroll in nurture

**Step 4: Create templates/partials/lead_row.html**

Single table row partial for HTMX swap on inline edit.

**Step 5: Test manually**

Run: `python app.py`
Navigate to `/leads`, verify table loads with seed data.
Click a lead, verify detail page loads.
Test search, filter, sort.

**Step 6: Commit**

```bash
git add app.py templates/
git commit -m "feat: leads table with search, filter, sort, and lead detail page"
```

---

### Task 6: Pipeline Kanban Board

**Files:**
- Modify: `app.py` (add routes)
- Create: `templates/pipeline.html`
- Create: `pipeline/deal_tracker.py`

**Step 1: Create pipeline/deal_tracker.py**

```python
from sqlalchemy.orm import Session
from database.models import Contact

PIPELINE_STAGES = ["New", "Contacted", "Qualified", "Proposal", "Negotiation", "Won", "Lost"]


def get_pipeline_data(db: Session) -> dict:
    """Return contacts grouped by pipeline stage."""
    pipeline = {}
    for stage in PIPELINE_STAGES:
        contacts = (
            db.query(Contact)
            .filter(Contact.lead_status == stage)
            .order_by(Contact.updated_at.desc())
            .all()
        )
        pipeline[stage] = contacts
    return pipeline


def move_deal(db: Session, contact_id: int, new_status: str) -> Contact:
    """Move a contact to a new pipeline stage."""
    contact = db.query(Contact).get(contact_id)
    if contact and new_status in PIPELINE_STAGES:
        contact.lead_status = new_status
        db.commit()
        db.refresh(contact)
    return contact


def get_pipeline_stats(db: Session) -> dict:
    """Pipeline summary statistics."""
    stats = {}
    for stage in PIPELINE_STAGES:
        contacts = db.query(Contact).filter(Contact.lead_status == stage).all()
        stats[stage] = {
            "count": len(contacts),
            "total_value": sum(c.deal_value or 0 for c in contacts),
        }
    return stats
```

**Step 2: Add pipeline routes to app.py**

- `GET /pipeline` — renders Kanban board
- `POST /pipeline/move` — moves deal between stages (HTMX, accepts `contact_id` and `new_status`)

**Step 3: Create templates/pipeline.html**

Kanban board with:
- 7 columns (one per stage) with color-coded headers
- Deal cards showing: Contact name, Company, Deal value, Days in stage
- Drag-and-drop via SortableJS (CDN) + HTMX POST on drop
- Stage totals in column headers (count + total value)
- Filter bar: assigned_to, deal value range

**Step 4: Test manually**

Navigate to `/pipeline`, verify Kanban loads with seed data in correct columns.
Drag a card to a new column, verify it persists.

**Step 5: Commit**

```bash
git add app.py pipeline/ templates/pipeline.html
git commit -m "feat: pipeline Kanban board with drag-and-drop stage management"
```

---

### Task 7: LinkedIn Scraper Engine

**Files:**
- Create: `scraper/linkedin.py`
- Create: `scraper/search_engine.py`
- Modify: `app.py` (add scraper routes)
- Create: `templates/scraper.html`
- Test: `tests/test_scraper.py`

**Step 1: Write the test (unit test for search_engine logic, not actual scraping)**

```python
# tests/test_scraper.py
from scraper.search_engine import build_linkedin_search_url, parse_icp_to_search_params


def test_build_search_url():
    url = build_linkedin_search_url(
        keywords=["steel", "fabrication"],
        location="Australia",
    )
    assert "linkedin.com" in url
    assert "steel" in url or "keywords" in url


def test_parse_icp_to_search_params():
    params = parse_icp_to_search_params(
        keywords=["steel", "corrosion"],
        countries=["AU"],
        states=["WA"],
    )
    assert "keywords" in params
    assert "location" in params
```

**Step 2: Create scraper/search_engine.py**

Orchestrator that:
- Accepts ICP criteria (keywords, location, company size)
- Builds LinkedIn search URLs
- Coordinates the Playwright scraper
- Deduplicates results against existing contacts in DB
- Returns structured lead data

**Step 3: Create scraper/linkedin.py**

Playwright-based scraper that:
- Logs into LinkedIn with stored credentials
- Navigates to LinkedIn Search (People search with filters)
- Extracts from search results: name, title, company, location, profile URL
- Visits individual profile pages for enrichment (summary, experience)
- Visits company pages for company data
- Implements rate limiting (random 2-5s delays)
- Returns list of dicts matching Contact/Company schema
- Handles pagination (next page of results)
- Stores session cookies to avoid re-login

**Step 4: Add scraper routes to app.py**

- `GET /scraper` — renders scraper page with ICP form
- `POST /scraper/start` — starts a scraping job (runs in background thread)
- `GET /scraper/status` — returns current scraping progress (HTMX polling)
- `POST /scraper/add/{index}` — adds a scraped lead to the database

**Step 5: Create templates/scraper.html**

Scraper UI with:
- ICP search form (pre-filled with Corrizon's keywords + locations)
- Editable fields: keywords (tag input), location, company size, max results
- "Start Scraping" button
- Live progress section (HTMX polling every 2s): "Scraping... found X leads so far"
- Results table: checkbox, Name, Title, Company, Location, LinkedIn URL, "Add" button
- "Add All Selected" bulk action

**Step 6: Run test**

Run: `pytest tests/test_scraper.py -v`
Expected: PASS

**Step 7: Manual integration test**

Run app, navigate to `/scraper`, fill in LinkedIn credentials in `.env`, start a scrape with limited results (5).
Verify leads appear in results table and can be added to DB.

**Step 8: Commit**

```bash
git add scraper/ app.py templates/scraper.html tests/test_scraper.py
git commit -m "feat: LinkedIn scraper with ICP-based search and live progress UI"
```

---

### Task 8: Meeting Scheduler

**Files:**
- Create: `scheduler/meeting.py`
- Modify: `app.py` (add routes)
- Create: `templates/scheduler.html`
- Test: `tests/test_meeting.py`

**Step 1: Write the test**

```python
# tests/test_meeting.py
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from database.db import Base
from database.models import Company, Contact, Meeting
from scheduler.meeting import create_meeting, get_upcoming_meetings, get_meetings_for_week


import pytest

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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_meeting.py -v`
Expected: FAIL

**Step 3: Create scheduler/meeting.py**

```python
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database.models import Meeting


def create_meeting(db: Session, contact_id: int, title: str, meeting_time: datetime,
                   duration_minutes: int = 30, agenda: str = "", location: str = "") -> Meeting:
    meeting = Meeting(
        contact_id=contact_id,
        title=title,
        meeting_time=meeting_time,
        duration_minutes=duration_minutes,
        agenda=agenda,
        location=location,
        status="Scheduled",
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting


def get_upcoming_meetings(db: Session, limit: int = 20) -> list[Meeting]:
    return (
        db.query(Meeting)
        .filter(Meeting.meeting_time >= datetime.utcnow())
        .filter(Meeting.status == "Scheduled")
        .order_by(Meeting.meeting_time.asc())
        .limit(limit)
        .all()
    )


def get_meetings_for_week(db: Session, start_date: datetime) -> list[Meeting]:
    end_date = start_date + timedelta(days=7)
    return (
        db.query(Meeting)
        .filter(Meeting.meeting_time >= start_date)
        .filter(Meeting.meeting_time < end_date)
        .order_by(Meeting.meeting_time.asc())
        .all()
    )


def update_meeting_status(db: Session, meeting_id: int, status: str) -> Meeting:
    meeting = db.query(Meeting).get(meeting_id)
    if meeting:
        meeting.status = status
        db.commit()
        db.refresh(meeting)
    return meeting
```

**Step 4: Add scheduler routes to app.py**

- `GET /scheduler` — calendar view with upcoming meetings
- `POST /scheduler/create` — create new meeting (form data)
- `PUT /scheduler/{id}` — update meeting
- `POST /scheduler/{id}/complete` — mark meeting completed
- `POST /scheduler/{id}/cancel` — cancel meeting

**Step 5: Create templates/scheduler.html**

Calendar UI with:
- Week view grid (7 columns, hour rows from 8am-6pm)
- Meeting blocks positioned by time
- "New Meeting" modal (select contact from dropdown, set time, agenda, location)
- Upcoming meetings sidebar list
- Click meeting → expand details + add notes

**Step 6: Run tests**

Run: `pytest tests/test_meeting.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add scheduler/ app.py templates/scheduler.html tests/test_meeting.py
git commit -m "feat: meeting scheduler with calendar view and CRUD"
```

---

### Task 9: Nurture Sequence Engine

**Files:**
- Create: `pipeline/nurture_engine.py`
- Modify: `app.py` (add routes)
- Create: `templates/nurture.html`
- Test: `tests/test_nurture.py`

**Step 1: Write the test**

```python
# tests/test_nurture.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from database.db import Base
from database.models import Company, Contact, NurtureSequence, NurtureEnrollment
from pipeline.nurture_engine import (
    enroll_contact, get_current_step_content, advance_step, get_enrollments_for_sequence,
)


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
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_nurture.py -v`
Expected: FAIL

**Step 3: Create pipeline/nurture_engine.py**

```python
from sqlalchemy.orm import Session
from database.models import Contact, NurtureSequence, NurtureEnrollment


def enroll_contact(db: Session, contact_id: int, sequence_id: int) -> NurtureEnrollment:
    enrollment = NurtureEnrollment(
        contact_id=contact_id,
        sequence_id=sequence_id,
        current_step=0,
        status="Active",
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment


def get_current_step_content(db: Session, enrollment_id: int) -> dict:
    enrollment = db.query(NurtureEnrollment).get(enrollment_id)
    seq = enrollment.sequence
    contact = enrollment.contact
    company = contact.company

    step = seq.steps[enrollment.current_step]
    body = step["body_template"].format(
        first_name=contact.first_name,
        last_name=contact.last_name or "",
        company_name=company.company_name if company else "",
        company_industry=company.company_industry if company else "",
        location_state=contact.location_state or "",
    )
    return {
        "subject": step["subject"],
        "body": body,
        "day_offset": step["day_offset"],
        "step_number": enrollment.current_step + 1,
        "total_steps": len(seq.steps),
    }


def advance_step(db: Session, enrollment_id: int) -> NurtureEnrollment:
    enrollment = db.query(NurtureEnrollment).get(enrollment_id)
    if enrollment.current_step + 1 >= len(enrollment.sequence.steps):
        enrollment.status = "Completed"
    else:
        enrollment.current_step += 1
    db.commit()
    db.refresh(enrollment)
    return enrollment


def get_enrollments_for_sequence(db: Session, sequence_id: int) -> list[NurtureEnrollment]:
    return (
        db.query(NurtureEnrollment)
        .filter(NurtureEnrollment.sequence_id == sequence_id)
        .order_by(NurtureEnrollment.enrolled_at.desc())
        .all()
    )


def get_active_enrollments(db: Session) -> list[NurtureEnrollment]:
    return (
        db.query(NurtureEnrollment)
        .filter(NurtureEnrollment.status == "Active")
        .all()
    )
```

**Step 4: Add nurture routes to app.py**

- `GET /nurture` — list all sequences and enrollments
- `POST /nurture/sequences` — create new sequence
- `GET /nurture/sequences/{id}` — view sequence details + enrolled contacts
- `POST /nurture/enroll` — enroll contact in sequence
- `GET /nurture/enrollments/{id}/preview` — preview current step email (HTMX)
- `POST /nurture/enrollments/{id}/advance` — advance to next step

**Step 5: Create templates/nurture.html**

Nurture UI with:
- Sequence list (cards showing name, step count, active enrollments)
- Click sequence → see steps timeline + enrolled contacts with current step
- "Enroll Contact" button opens modal (select contact dropdown)
- Step preview panel: shows rendered email for selected enrollment
- "Mark Step Complete / Advance" button

**Step 6: Run tests**

Run: `pytest tests/test_nurture.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add pipeline/nurture_engine.py app.py templates/nurture.html tests/test_nurture.py
git commit -m "feat: nurture sequence engine with enrollment, templating, and step advancement"
```

---

### Task 10: Proposal Generator (PDF + Email)

**Files:**
- Create: `proposals/pdf_generator.py`
- Create: `proposals/email_generator.py`
- Create: `proposals/templates/proposal.html`
- Create: `proposals/templates/email.html`
- Modify: `app.py` (add routes)
- Create: `templates/proposals.html`
- Test: `tests/test_proposals.py`

**Step 1: Write the test**

```python
# tests/test_proposals.py
import pytest
from proposals.email_generator import render_email_proposal


def test_render_email_proposal():
    html = render_email_proposal(
        contact_name="John Smith",
        company_name="WA Steel Fabricators",
        products=[
            {"name": "CorrShield Base Coat", "description": "Zinc-rich primer", "quantity": "50L", "unit_price": 45.00, "total": 2250.00},
        ],
        total_price=2250.00,
        notes="Includes free shipping to Perth.",
    )
    assert "John Smith" in html
    assert "WA Steel Fabricators" in html
    assert "CorrShield Base Coat" in html
    assert "2,250" in html
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_proposals.py -v`
Expected: FAIL

**Step 3: Create proposals/templates/proposal.html**

WeasyPrint-compatible HTML template for the PDF:
- Corrizon branded header (navy/amber)
- "PROPOSAL" title, date, proposal number
- "Prepared for: [Contact Name], [Company Name]"
- Product/service table: Item, Description, Qty, Unit Price, Total
- Total pricing row
- Corrizon key differentiators section
- Terms & conditions footer
- Contact details footer

**Step 4: Create proposals/templates/email.html**

Lighter email-style HTML:
- Corrizon header
- Personalized greeting
- Brief product summary
- Pricing table
- CTA: "Let's schedule a call to discuss"
- Corrizon signature

**Step 5: Create proposals/pdf_generator.py**

```python
import os
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from config import settings


proposal_env = Environment(loader=FileSystemLoader("proposals/templates"))


def generate_pdf_proposal(
    contact_name: str,
    company_name: str,
    products: list[dict],
    total_price: float,
    notes: str = "",
    proposal_number: str = None,
) -> str:
    if not proposal_number:
        proposal_number = f"COR-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    template = proposal_env.get_template("proposal.html")
    html_content = template.render(
        company=settings.company_name,
        website=settings.company_website,
        contact_name=contact_name,
        company_name=company_name,
        products=products,
        total_price=total_price,
        notes=notes,
        proposal_number=proposal_number,
        date=datetime.now().strftime("%d %B %Y"),
        differentiators=settings.key_differentiators,
    )

    output_dir = "output/proposals"
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, f"{proposal_number}.pdf")
    HTML(string=html_content).write_pdf(pdf_path)
    return pdf_path
```

**Step 6: Create proposals/email_generator.py**

```python
from jinja2 import Environment, FileSystemLoader
from config import settings

proposal_env = Environment(loader=FileSystemLoader("proposals/templates"))


def render_email_proposal(
    contact_name: str,
    company_name: str,
    products: list[dict],
    total_price: float,
    notes: str = "",
) -> str:
    template = proposal_env.get_template("email.html")
    return template.render(
        company=settings.company_name,
        website=settings.company_website,
        contact_name=contact_name,
        company_name=company_name,
        products=products,
        total_price=total_price,
        notes=notes,
        differentiators=settings.key_differentiators,
    )
```

**Step 7: Add proposal routes to app.py**

- `GET /proposals` — list all proposals + create new
- `POST /proposals/create` — create proposal (select contact, choose products, set pricing)
- `GET /proposals/{id}` — view proposal details
- `GET /proposals/{id}/pdf` — download generated PDF
- `GET /proposals/{id}/email-preview` — preview email HTML (HTMX)
- `POST /proposals/{id}/send` — mark as sent (updates status + timestamp)

**Step 8: Create templates/proposals.html**

Proposal UI with:
- Proposal list (cards: contact, company, value, status, date)
- "New Proposal" form: select contact (auto-fills company), product checklist with quantities, custom pricing override, notes
- Preview pane: toggle between PDF preview (iframe) and email preview
- Action buttons: Download PDF, Copy Email HTML, Mark as Sent

**Step 9: Run tests**

Run: `pytest tests/test_proposals.py -v`
Expected: PASS

**Step 10: Commit**

```bash
git add proposals/ app.py templates/proposals.html tests/test_proposals.py
git commit -m "feat: proposal generator with PDF and HTML email output"
```

---

### Task 11: Web Enrichment Module

**Files:**
- Create: `scraper/web_enricher.py`
- Test: `tests/test_enricher.py`

**Step 1: Write the test**

```python
# tests/test_enricher.py
from scraper.web_enricher import extract_domain_from_url, build_email_guess


def test_extract_domain():
    assert extract_domain_from_url("https://www.wasteel.com.au/about") == "wasteel.com.au"
    assert extract_domain_from_url("http://scengineering.com.au") == "scengineering.com.au"


def test_build_email_guess():
    guesses = build_email_guess("John", "Smith", "wasteel.com.au")
    assert "john.smith@wasteel.com.au" in guesses
    assert "jsmith@wasteel.com.au" in guesses
    assert "john@wasteel.com.au" in guesses
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_enricher.py -v`
Expected: FAIL

**Step 3: Create scraper/web_enricher.py**

```python
from urllib.parse import urlparse


def extract_domain_from_url(url: str) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    parsed = urlparse(url)
    domain = parsed.netloc
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def build_email_guess(first_name: str, last_name: str, domain: str) -> list[str]:
    first = first_name.lower().strip()
    last = last_name.lower().strip()
    return [
        f"{first}.{last}@{domain}",
        f"{first[0]}{last}@{domain}",
        f"{first}@{domain}",
        f"{first}_{last}@{domain}",
        f"{first}{last[0]}@{domain}",
    ]
```

**Step 4: Run tests**

Run: `pytest tests/test_enricher.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scraper/web_enricher.py tests/test_enricher.py
git commit -m "feat: web enricher with domain extraction and email guessing"
```

---

### Task 12: Polish & Integration Testing

**Files:**
- Modify: `app.py` (add .env template, startup message)
- Create: `.env.example`
- Create: `.gitignore`
- Update: `templates/base.html` (nav active states, responsive)
- Create: `tests/test_app.py`

**Step 1: Create .env.example**

```
LINKEDIN_EMAIL=your-linkedin-email@example.com
LINKEDIN_PASSWORD=your-linkedin-password
DEBUG=true
```

**Step 2: Create .gitignore**

```
venv/
__pycache__/
*.pyc
.env
mastersales.db
output/proposals/*.pdf
.pytest_cache/
```

**Step 3: Write integration test**

```python
# tests/test_app.py
import pytest
from fastapi.testclient import TestClient
from app import app


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def test_dashboard_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "MasterSales" in response.text


def test_leads_page_loads(client):
    response = client.get("/leads")
    assert response.status_code == 200


def test_pipeline_page_loads(client):
    response = client.get("/pipeline")
    assert response.status_code == 200


def test_scraper_page_loads(client):
    response = client.get("/scraper")
    assert response.status_code == 200


def test_scheduler_page_loads(client):
    response = client.get("/scheduler")
    assert response.status_code == 200


def test_nurture_page_loads(client):
    response = client.get("/nurture")
    assert response.status_code == 200


def test_proposals_page_loads(client):
    response = client.get("/proposals")
    assert response.status_code == 200
```

**Step 4: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL tests pass

**Step 5: Add startup banner to app.py**

Print:
```
🚀 MasterSales — Sales Activation Platform
   Company: Corrizon Australasia Pty Ltd
   Open: http://127.0.0.1:8000
```

**Step 6: Final manual walkthrough**

1. `python app.py` — app starts, dashboard loads
2. Click through all 7 pages
3. Add a lead, move through pipeline
4. Schedule a meeting
5. Create a proposal, download PDF
6. View nurture sequences

**Step 7: Commit**

```bash
git add -A
git commit -m "feat: integration tests, .env setup, .gitignore, startup polish"
```

---

## Summary

| Task | Component | Estimated Complexity |
|------|-----------|---------------------|
| 1 | Project scaffolding | Low |
| 2 | Database models | Medium |
| 3 | Seed data | Medium |
| 4 | App skeleton + dashboard | Medium |
| 5 | Leads table + detail | High |
| 6 | Pipeline Kanban | High |
| 7 | LinkedIn scraper | High |
| 8 | Meeting scheduler | Medium |
| 9 | Nurture engine | Medium |
| 10 | Proposal generator | High |
| 11 | Web enricher | Low |
| 12 | Polish + integration tests | Medium |

**Total: 12 tasks, ~60 steps**

Each task produces a working, committed increment. The app is functional from Task 4 onward.
