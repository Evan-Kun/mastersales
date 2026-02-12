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
