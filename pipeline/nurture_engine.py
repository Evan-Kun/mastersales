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
