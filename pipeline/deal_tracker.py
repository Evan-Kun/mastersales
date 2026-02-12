from sqlalchemy.orm import Session
from database.models import Contact

PIPELINE_STAGES = ["New", "Contacted", "Qualified", "Proposal", "Negotiation", "Won", "Lost"]


def get_pipeline_data(db: Session) -> dict:
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
    contact = db.query(Contact).get(contact_id)
    if contact and new_status in PIPELINE_STAGES:
        contact.lead_status = new_status
        db.commit()
        db.refresh(contact)
    return contact


def get_pipeline_stats(db: Session) -> dict:
    stats = {}
    for stage in PIPELINE_STAGES:
        contacts = db.query(Contact).filter(Contact.lead_status == stage).all()
        stats[stage] = {
            "count": len(contacts),
            "total_value": sum(c.deal_value or 0 for c in contacts),
        }
    return stats
