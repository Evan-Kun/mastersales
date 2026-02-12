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
