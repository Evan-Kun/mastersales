import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_

from config import settings
from database.db import init_db, get_db, SessionLocal
from database.models import (
    Company, Contact, Meeting, Proposal, NurtureSequence, NurtureEnrollment,
)
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


# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mastersales")

app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ── Dashboard ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
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

    total_pipeline_value = sum(
        c.deal_value or 0
        for c in db.query(Contact).filter(Contact.deal_value.isnot(None)).all()
    )

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "settings": settings,
        "total_leads": total_leads,
        "active_deals": active_deals,
        "proposals_sent": proposals_sent,
        "meetings_count": meetings_count,
        "recent_leads": recent_leads,
        "pipeline_counts": pipeline_counts,
        "total_pipeline_value": total_pipeline_value,
    })


# ── Leads ──────────────────────────────────────────────────────────────────────

@app.get("/leads", response_class=HTMLResponse)
def leads_list(
    request: Request,
    db: Session = Depends(get_db),
    q: str = "",
    status: str = "",
    state: str = "",
    sort: str = "created_at",
    order: str = "desc",
):
    query = db.query(Contact).join(Company, isouter=True)

    if q:
        query = query.filter(
            or_(
                Contact.first_name.ilike(f"%{q}%"),
                Contact.last_name.ilike(f"%{q}%"),
                Contact.job_title.ilike(f"%{q}%"),
                Contact.email_work.ilike(f"%{q}%"),
                Company.company_name.ilike(f"%{q}%"),
            )
        )
    if status:
        query = query.filter(Contact.lead_status == status)
    if state:
        query = query.filter(Contact.location_state == state)

    sort_col = getattr(Contact, sort, Contact.created_at)
    if order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    contacts = query.all()

    statuses = ["New", "Contacted", "Qualified", "Proposal", "Negotiation", "Won", "Lost"]
    states = sorted(set(c.location_state for c in db.query(Contact).all() if c.location_state))

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/leads_table_body.html", {
            "request": request,
            "contacts": contacts,
        })

    return templates.TemplateResponse("leads.html", {
        "request": request,
        "settings": settings,
        "contacts": contacts,
        "statuses": statuses,
        "states": states,
        "q": q,
        "current_status": status,
        "current_state": state,
        "sort": sort,
        "order": order,
    })


@app.get("/leads/{contact_id}", response_class=HTMLResponse)
def lead_detail(request: Request, contact_id: int, db: Session = Depends(get_db)):
    contact = db.query(Contact).get(contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    meetings = db.query(Meeting).filter(Meeting.contact_id == contact_id).order_by(Meeting.meeting_time.desc()).all()
    proposals = db.query(Proposal).filter(Proposal.contact_id == contact_id).order_by(Proposal.created_at.desc()).all()
    enrollments = db.query(NurtureEnrollment).filter(NurtureEnrollment.contact_id == contact_id).all()
    sequences = db.query(NurtureSequence).all()

    return templates.TemplateResponse("lead_detail.html", {
        "request": request,
        "settings": settings,
        "contact": contact,
        "meetings": meetings,
        "proposals": proposals,
        "enrollments": enrollments,
        "sequences": sequences,
    })


@app.post("/leads/{contact_id}/update", response_class=HTMLResponse)
def lead_update(
    request: Request,
    contact_id: int,
    db: Session = Depends(get_db),
    lead_status: str = Form(None),
    lead_score: int = Form(None),
    deal_value: float = Form(None),
    notes: str = Form(None),
    assigned_to: str = Form(None),
):
    contact = db.query(Contact).get(contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    if lead_status is not None:
        contact.lead_status = lead_status
    if lead_score is not None:
        contact.lead_score = lead_score
    if deal_value is not None:
        contact.deal_value = deal_value
    if notes is not None:
        contact.notes = notes
    if assigned_to is not None:
        contact.assigned_to = assigned_to

    db.commit()

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/lead_status_badge.html", {
            "request": request,
            "contact": contact,
        })

    return RedirectResponse(f"/leads/{contact_id}", status_code=303)


# ── Pipeline ───────────────────────────────────────────────────────────────────

PIPELINE_STAGES = ["New", "Contacted", "Qualified", "Proposal", "Negotiation", "Won", "Lost"]


@app.get("/pipeline", response_class=HTMLResponse)
def pipeline(request: Request, db: Session = Depends(get_db)):
    pipeline_data = {}
    pipeline_stats = {}
    for stage in PIPELINE_STAGES:
        contacts = (
            db.query(Contact)
            .filter(Contact.lead_status == stage)
            .order_by(Contact.updated_at.desc())
            .all()
        )
        pipeline_data[stage] = contacts
        pipeline_stats[stage] = {
            "count": len(contacts),
            "total_value": sum(c.deal_value or 0 for c in contacts),
        }

    return templates.TemplateResponse("pipeline.html", {
        "request": request,
        "settings": settings,
        "pipeline_data": pipeline_data,
        "pipeline_stats": pipeline_stats,
        "stages": PIPELINE_STAGES,
    })


@app.post("/pipeline/move", response_class=HTMLResponse)
def pipeline_move(
    request: Request,
    db: Session = Depends(get_db),
    contact_id: int = Form(...),
    new_status: str = Form(...),
):
    contact = db.query(Contact).get(contact_id)
    if contact and new_status in PIPELINE_STAGES:
        contact.lead_status = new_status
        db.commit()

    pipeline_stats = {}
    for stage in PIPELINE_STAGES:
        contacts = db.query(Contact).filter(Contact.lead_status == stage).all()
        pipeline_stats[stage] = {
            "count": len(contacts),
            "total_value": sum(c.deal_value or 0 for c in contacts),
        }

    return templates.TemplateResponse("partials/pipeline_stats.html", {
        "request": request,
        "pipeline_stats": pipeline_stats,
        "stages": PIPELINE_STAGES,
    })


# ── Scraper ────────────────────────────────────────────────────────────────────

scraper_results: list[dict] = []
scraper_status: dict = {"running": False, "found": 0, "message": "Idle"}


@app.get("/scraper", response_class=HTMLResponse)
def scraper_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("scraper.html", {
        "request": request,
        "settings": settings,
        "scraper_status": scraper_status,
        "results": scraper_results,
    })


@app.post("/scraper/start", response_class=HTMLResponse)
def scraper_start(
    request: Request,
    keywords: str = Form(""),
    location: str = Form("Australia"),
    max_results: int = Form(20),
):
    import threading
    from scraper.search_engine import run_scrape

    scraper_results.clear()
    scraper_status.update({"running": True, "found": 0, "message": "Starting scrape..."})

    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]
    if not keyword_list:
        keyword_list = settings.industry_keywords[:5]

    logger.info(f"WEB: Scrape requested — keywords={keyword_list}, location={location}, max={max_results}")

    def _scrape():
        try:
            results = run_scrape(keyword_list, location, max_results)
            scraper_results.extend(results)
            scraper_status.update({"running": False, "found": len(results), "message": f"Complete. Found {len(results)} leads."})
            logger.info(f"WEB: Scrape finished — {len(results)} leads found")
        except Exception as e:
            scraper_status.update({"running": False, "found": 0, "message": f"Error: {str(e)}"})
            logger.error(f"WEB: Scrape failed — {e}")

    thread = threading.Thread(target=_scrape, daemon=True)
    thread.start()

    return templates.TemplateResponse("partials/scraper_status.html", {
        "request": request,
        "scraper_status": scraper_status,
        "results": scraper_results,
    })


@app.get("/scraper/status", response_class=HTMLResponse)
def scraper_status_check(request: Request):
    return templates.TemplateResponse("partials/scraper_status.html", {
        "request": request,
        "scraper_status": scraper_status,
        "results": scraper_results,
    })


def _add_scraper_result_to_db(index: int, db: Session) -> tuple[dict | None, str]:
    """Save a single scraper result to the database.

    Returns (result_dict, status) where status is 'added', 'duplicate', or 'error'.
    """
    if index < 0 or index >= len(scraper_results):
        return None, "error"

    result = scraper_results[index]

    # Check for duplicate by linkedin_url OR by first+last name
    existing = None
    if result.get("linkedin_url"):
        existing = db.query(Contact).filter(Contact.linkedin_url == result["linkedin_url"]).first()
    if not existing and result.get("first_name") and result.get("last_name"):
        existing = db.query(Contact).filter(
            Contact.first_name == result["first_name"],
            Contact.last_name == result["last_name"],
        ).first()

    if existing:
        return result, "duplicate"

    # Find or create company
    company = None
    if result.get("company_name"):
        company = db.query(Company).filter(Company.company_name == result["company_name"]).first()
        if not company:
            company = Company(
                company_name=result.get("company_name", ""),
                company_industry=result.get("company_industry", ""),
                company_location=result.get("company_location", ""),
                company_linkedin_url=result.get("company_linkedin_url"),
            )
            db.add(company)
            db.flush()

    contact = Contact(
        first_name=result.get("first_name", ""),
        last_name=result.get("last_name", ""),
        job_title=result.get("job_title", ""),
        linkedin_url=result.get("linkedin_url"),
        location_city=result.get("location_city", ""),
        location_state=result.get("location_state", ""),
        location_country=result.get("location_country", "AU"),
        lead_status="New",
        lead_source="LinkedIn",
        company_id=company.id if company else None,
    )
    db.add(contact)

    return result, "added"


@app.post("/scraper/add/{index}", response_class=HTMLResponse)
def scraper_add_lead(request: Request, index: int, db: Session = Depends(get_db)):
    result, status = _add_scraper_result_to_db(index, db)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    db.commit()

    loc = result.get("location_city", "")
    if result.get("location_state"):
        loc += f", {result['location_state']}"

    return templates.TemplateResponse("partials/scraper_row_added.html", {
        "request": request,
        "index": index,
        "num": index + 1,
        "name": f"{result.get('first_name', '')} {result.get('last_name', '')}",
        "title": result.get("job_title", "-"),
        "company": result.get("company_name", "-"),
        "location": loc,
        "status": status,
    })


@app.post("/scraper/add-bulk", response_class=HTMLResponse)
def scraper_add_bulk(request: Request, indices: list[int] = Form(...), db: Session = Depends(get_db)):
    added = 0
    duplicates = 0
    for idx in indices:
        result, status = _add_scraper_result_to_db(idx, db)
        if status == "added":
            added += 1
        elif status == "duplicate":
            duplicates += 1
    db.commit()

    msg = f"Added {added} leads to your CRM."
    if duplicates:
        msg += f" {duplicates} already existed (skipped)."
    logger.info(f"WEB: Bulk add — {added} new, {duplicates} duplicates")

    return templates.TemplateResponse("partials/scraper_status.html", {
        "request": request,
        "scraper_status": {"running": False, "found": scraper_status.get("found", 0), "message": msg},
        "results": scraper_results,
        "added_indices": indices,
    })


# ── Scheduler ──────────────────────────────────────────────────────────────────

@app.get("/scheduler", response_class=HTMLResponse)
def scheduler_page(request: Request, db: Session = Depends(get_db)):
    upcoming = (
        db.query(Meeting)
        .filter(Meeting.meeting_time >= datetime.utcnow())
        .filter(Meeting.status == "Scheduled")
        .order_by(Meeting.meeting_time.asc())
        .limit(20)
        .all()
    )
    past = (
        db.query(Meeting)
        .filter(Meeting.meeting_time < datetime.utcnow())
        .order_by(Meeting.meeting_time.desc())
        .limit(10)
        .all()
    )
    contacts = db.query(Contact).order_by(Contact.first_name).all()

    today = datetime.utcnow().date()
    week_start = today - timedelta(days=today.weekday())
    week_dates = [week_start + timedelta(days=i) for i in range(7)]

    week_meetings = (
        db.query(Meeting)
        .filter(Meeting.meeting_time >= datetime.combine(week_start, datetime.min.time()))
        .filter(Meeting.meeting_time < datetime.combine(week_start + timedelta(days=7), datetime.min.time()))
        .all()
    )

    return templates.TemplateResponse("scheduler.html", {
        "request": request,
        "settings": settings,
        "upcoming": upcoming,
        "past": past,
        "contacts": contacts,
        "week_dates": week_dates,
        "week_meetings": week_meetings,
    })


@app.post("/scheduler/create")
def scheduler_create(
    db: Session = Depends(get_db),
    contact_id: int = Form(...),
    title: str = Form(...),
    meeting_date: str = Form(...),
    meeting_time_str: str = Form(...),
    duration_minutes: int = Form(30),
    location: str = Form(""),
    agenda: str = Form(""),
):
    meeting_time = datetime.strptime(f"{meeting_date} {meeting_time_str}", "%Y-%m-%d %H:%M")
    meeting = Meeting(
        contact_id=contact_id,
        title=title,
        meeting_time=meeting_time,
        duration_minutes=duration_minutes,
        location=location,
        agenda=agenda,
        status="Scheduled",
    )
    db.add(meeting)
    db.commit()
    return RedirectResponse("/scheduler", status_code=303)


@app.post("/scheduler/{meeting_id}/complete")
def scheduler_complete(meeting_id: int, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).get(meeting_id)
    if meeting:
        meeting.status = "Completed"
        db.commit()
    return RedirectResponse("/scheduler", status_code=303)


@app.post("/scheduler/{meeting_id}/cancel")
def scheduler_cancel(meeting_id: int, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).get(meeting_id)
    if meeting:
        meeting.status = "Cancelled"
        db.commit()
    return RedirectResponse("/scheduler", status_code=303)


# ── Nurture ────────────────────────────────────────────────────────────────────

@app.get("/nurture", response_class=HTMLResponse)
def nurture_page(request: Request, db: Session = Depends(get_db)):
    sequences = db.query(NurtureSequence).all()
    enrollments = db.query(NurtureEnrollment).all()
    contacts = db.query(Contact).order_by(Contact.first_name).all()

    return templates.TemplateResponse("nurture.html", {
        "request": request,
        "settings": settings,
        "sequences": sequences,
        "enrollments": enrollments,
        "contacts": contacts,
    })


@app.post("/nurture/enroll")
def nurture_enroll(
    db: Session = Depends(get_db),
    contact_id: int = Form(...),
    sequence_id: int = Form(...),
):
    enrollment = NurtureEnrollment(
        contact_id=contact_id,
        sequence_id=sequence_id,
        current_step=0,
        status="Active",
    )
    db.add(enrollment)
    db.commit()
    return RedirectResponse("/nurture", status_code=303)


@app.get("/nurture/enrollments/{enrollment_id}/preview", response_class=HTMLResponse)
def nurture_preview(request: Request, enrollment_id: int, db: Session = Depends(get_db)):
    enrollment = db.query(NurtureEnrollment).get(enrollment_id)
    if not enrollment:
        raise HTTPException(status_code=404)

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

    return templates.TemplateResponse("partials/nurture_preview.html", {
        "request": request,
        "step": step,
        "body": body,
        "enrollment": enrollment,
        "step_number": enrollment.current_step + 1,
        "total_steps": len(seq.steps),
    })


@app.post("/nurture/enrollments/{enrollment_id}/advance")
def nurture_advance(enrollment_id: int, db: Session = Depends(get_db)):
    enrollment = db.query(NurtureEnrollment).get(enrollment_id)
    if not enrollment:
        raise HTTPException(status_code=404)

    if enrollment.current_step + 1 >= len(enrollment.sequence.steps):
        enrollment.status = "Completed"
    else:
        enrollment.current_step += 1
    db.commit()
    return RedirectResponse("/nurture", status_code=303)


# ── Proposals ──────────────────────────────────────────────────────────────────

@app.get("/proposals", response_class=HTMLResponse)
def proposals_page(request: Request, db: Session = Depends(get_db)):
    proposals = db.query(Proposal).order_by(Proposal.created_at.desc()).all()
    contacts = db.query(Contact).order_by(Contact.first_name).all()

    return templates.TemplateResponse("proposals.html", {
        "request": request,
        "settings": settings,
        "proposals": proposals,
        "contacts": contacts,
        "products": settings.products,
    })


@app.post("/proposals/create")
def proposals_create(
    request: Request,
    db: Session = Depends(get_db),
    contact_id: int = Form(...),
    products: list[str] = Form([]),
    quantities: list[str] = Form([]),
    notes: str = Form(""),
):
    contact = db.query(Contact).get(contact_id)
    if not contact:
        raise HTTPException(status_code=404)

    product_list = []
    total = 0.0
    for i, product_name in enumerate(products):
        product_info = next((p for p in settings.products if p["name"] == product_name), None)
        if product_info:
            qty = float(quantities[i]) if i < len(quantities) and quantities[i] else 1
            line_total = product_info["price_per_litre"] * qty
            product_list.append({
                "name": product_info["name"],
                "description": product_info["description"],
                "quantity": qty,
                "unit_price": product_info["price_per_litre"],
                "total": line_total,
            })
            total += line_total

    proposal = Proposal(
        contact_id=contact_id,
        products=product_list,
        pricing=total,
        status="Draft",
    )
    db.add(proposal)
    db.commit()

    # Generate PDF
    try:
        from proposals.pdf_generator import generate_pdf_proposal
        company = contact.company
        pdf_path = generate_pdf_proposal(
            contact_name=f"{contact.first_name} {contact.last_name or ''}".strip(),
            company_name=company.company_name if company else "",
            products=product_list,
            total_price=total,
            notes=notes,
        )
        proposal.pdf_path = pdf_path
    except Exception:
        pass

    # Generate email HTML
    try:
        from proposals.email_generator import render_email_proposal
        company = contact.company
        email_html = render_email_proposal(
            contact_name=f"{contact.first_name} {contact.last_name or ''}".strip(),
            company_name=company.company_name if company else "",
            products=product_list,
            total_price=total,
            notes=notes,
        )
        proposal.email_html = email_html
    except Exception:
        pass

    db.commit()
    return RedirectResponse("/proposals", status_code=303)


@app.get("/proposals/{proposal_id}/pdf")
def proposals_download_pdf(proposal_id: int, db: Session = Depends(get_db)):
    proposal = db.query(Proposal).get(proposal_id)
    if not proposal or not proposal.pdf_path:
        raise HTTPException(status_code=404)
    return FileResponse(proposal.pdf_path, media_type="application/pdf", filename=f"proposal-{proposal_id}.pdf")


@app.get("/proposals/{proposal_id}/email-preview", response_class=HTMLResponse)
def proposals_email_preview(request: Request, proposal_id: int, db: Session = Depends(get_db)):
    proposal = db.query(Proposal).get(proposal_id)
    if not proposal or not proposal.email_html:
        raise HTTPException(status_code=404)
    return HTMLResponse(proposal.email_html)


@app.post("/proposals/{proposal_id}/send")
def proposals_mark_sent(proposal_id: int, db: Session = Depends(get_db)):
    proposal = db.query(Proposal).get(proposal_id)
    if proposal:
        proposal.status = "Sent"
        proposal.sent_at = datetime.utcnow()
        db.commit()
    return RedirectResponse("/proposals", status_code=303)


# ── Run ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 60)
    print("  MasterSales - Sales Activation Platform")
    print(f"  Company: {settings.company_name}")
    print("  Open: http://127.0.0.1:8899")
    print("=" * 60 + "\n")
    uvicorn.run("app:app", host="127.0.0.1", port=8899, reload=True)
