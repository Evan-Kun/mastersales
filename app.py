import csv
import io
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI, Request, Depends, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_

from config import settings
from database.db import init_db, get_db, SessionLocal
from database.models import (
    Company, Contact, Meeting, Proposal, NurtureSequence, NurtureEnrollment, User,
)
from database.seed import seed_demo_data
from auth import (
    hash_password, verify_password, require_auth, get_current_user,
    create_reset_token, verify_reset_token,
    set_session_cookie, clear_session_cookie, _AuthRedirect,
)


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

# ── Source badge CSS helper ────────────────────────────────────────────────────

SOURCE_BADGE_CSS = {
    "LinkedIn": "bg-sky-100 text-sky-700",
    "ACA": "bg-emerald-100 text-emerald-700",
    "AMPP": "bg-orange-100 text-orange-700",
    "AusTender": "bg-violet-100 text-violet-700",
    "QTenders": "bg-violet-100 text-violet-700",
    "eTendering": "bg-violet-100 text-violet-700",
    "Tenders VIC": "bg-violet-100 text-violet-700",
    "GEMS WA": "bg-violet-100 text-violet-700",
    "GETS": "bg-indigo-100 text-indigo-700",
}
_DEFAULT_BADGE = "bg-amber-100 text-amber-700"

def get_source_badge_css(source_name: str) -> str:
    for key, css in SOURCE_BADGE_CSS.items():
        if source_name.startswith(key):
            return css
    if "Trade Show" in source_name:
        return _DEFAULT_BADGE
    return "bg-gray-100 text-gray-700"


# ── Auth middleware ────────────────────────────────────────────────────────────

PUBLIC_PATHS = {"/login", "/signup", "/forgot-password", "/reset-password"}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    # Allow static files and auth pages through
    if path.startswith("/static") or path in PUBLIC_PATHS:
        return await call_next(request)
    # Check session cookie
    from auth import read_session_cookie, SESSION_COOKIE
    token = request.cookies.get(SESSION_COOKIE)
    user_id = read_session_cookie(token) if token else None
    if not user_id:
        return RedirectResponse("/login", status_code=303)
    # Store user_id on request state so templates can access it
    request.state.user_id = user_id
    return await call_next(request)


@app.exception_handler(_AuthRedirect)
async def auth_redirect_handler(request: Request, exc: _AuthRedirect):
    return RedirectResponse("/login", status_code=303)


# ── Auth routes ───────────────────────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, reset: str = ""):
    ctx = {"request": request}
    if reset == "success":
        ctx["success"] = "Password reset successfully. Please sign in."
    return templates.TemplateResponse("auth/login.html", ctx)


@app.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(...),
    password: str = Form(...),
):
    user = db.query(User).filter(User.email == email.lower().strip()).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "Invalid email or password.",
            "email": email,
        })
    if not user.is_active:
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "This account has been deactivated.",
            "email": email,
        })
    response = RedirectResponse("/", status_code=303)
    return set_session_cookie(response, user.id)


@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    return templates.TemplateResponse("auth/signup.html", {"request": request})


@app.post("/signup", response_class=HTMLResponse)
def signup_submit(
    request: Request,
    db: Session = Depends(get_db),
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
):
    email_clean = email.lower().strip()
    ctx = {"request": request, "full_name": full_name, "email": email}

    if len(password) < 8:
        return templates.TemplateResponse("auth/signup.html", {
            **ctx, "error": "Password must be at least 8 characters."})
    if password != password_confirm:
        return templates.TemplateResponse("auth/signup.html", {
            **ctx, "error": "Passwords do not match."})
    if db.query(User).filter(User.email == email_clean).first():
        return templates.TemplateResponse("auth/signup.html", {
            **ctx, "error": "An account with this email already exists."})

    user = User(
        email=email_clean,
        full_name=full_name.strip(),
        password_hash=hash_password(password),
    )
    db.add(user)
    db.commit()

    response = RedirectResponse("/", status_code=303)
    return set_session_cookie(response, user.id)


@app.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    return templates.TemplateResponse("auth/forgot_password.html", {"request": request})


@app.post("/forgot-password", response_class=HTMLResponse)
def forgot_password_submit(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(...),
):
    user = db.query(User).filter(User.email == email.lower().strip()).first()
    if user:
        token = create_reset_token(user.email)
        reset_url = f"{request.base_url}reset-password?token={token}"
        logger.info(f"AUTH: Password reset link for {user.email}: {reset_url}")
    # Always show success to prevent email enumeration
    return templates.TemplateResponse("auth/forgot_password.html", {
        "request": request,
        "success": "If an account with that email exists, a reset link has been sent. Check the server logs for the link.",
    })


@app.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request, token: str = ""):
    if not token or not verify_reset_token(token):
        return templates.TemplateResponse("auth/reset_password.html", {
            "request": request, "invalid_token": True})
    return templates.TemplateResponse("auth/reset_password.html", {
        "request": request, "token": token})


@app.post("/reset-password", response_class=HTMLResponse)
def reset_password_submit(
    request: Request,
    db: Session = Depends(get_db),
    token: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
):
    email = verify_reset_token(token)
    if not email:
        return templates.TemplateResponse("auth/reset_password.html", {
            "request": request, "invalid_token": True})

    if len(password) < 8:
        return templates.TemplateResponse("auth/reset_password.html", {
            "request": request, "token": token,
            "error": "Password must be at least 8 characters."})
    if password != password_confirm:
        return templates.TemplateResponse("auth/reset_password.html", {
            "request": request, "token": token,
            "error": "Passwords do not match."})

    user = db.query(User).filter(User.email == email).first()
    if user:
        user.password_hash = hash_password(password)
        db.commit()

    return RedirectResponse("/login?reset=success", status_code=303)


@app.post("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    return clear_session_cookie(response)


# ── Helper: get current user for templates ────────────────────────────────────

def _get_user(request: Request, db: Session) -> User | None:
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return db.query(User).get(user_id)
    return None


# ── Helper: active contacts query (excludes soft-deleted) ─────────────────────

def _active_contacts(db: Session):
    """Return a query for contacts that have NOT been soft-deleted."""
    return db.query(Contact).filter(Contact.deleted_at.is_(None))


# ── Users ──────────────────────────────────────────────────────────────────────

@app.get("/users", response_class=HTMLResponse)
def users_list(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    all_users = db.query(User).order_by(User.created_at.desc()).all()
    return templates.TemplateResponse("users.html", {
        "request": request, "settings": settings, "user": user,
        "users": all_users,
    })


# ── Dashboard ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    total_leads = _active_contacts(db).count()
    active_deals = _active_contacts(db).filter(
        Contact.lead_status.in_(["Qualified", "Proposal", "Negotiation"])
    ).count()
    proposals_sent = db.query(Proposal).filter(Proposal.status != "Draft").count()
    meetings_count = db.query(Meeting).count()

    recent_leads = _active_contacts(db).order_by(Contact.created_at.desc()).limit(5).all()

    pipeline_counts = {}
    for status in ["New", "Contacted", "Qualified", "Proposal", "Negotiation", "Won", "Lost"]:
        pipeline_counts[status] = _active_contacts(db).filter(Contact.lead_status == status).count()

    total_pipeline_value = sum(
        c.deal_value or 0
        for c in _active_contacts(db).filter(Contact.deal_value.isnot(None)).all()
    )

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "settings": settings,
        "user": _get_user(request, db),
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
    query = _active_contacts(db).join(Company, isouter=True)

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
    states = sorted(set(c.location_state for c in _active_contacts(db).all() if c.location_state))

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/leads_table_body.html", {
            "request": request,
            "contacts": contacts,
        })

    return templates.TemplateResponse("leads.html", {
        "request": request,
        "settings": settings,
        "user": _get_user(request, db),
        "contacts": contacts,
        "statuses": statuses,
        "states": states,
        "q": q,
        "current_status": status,
        "current_state": state,
        "sort": sort,
        "order": order,
    })


CSV_COLUMNS = [
    "First Name", "Last Name", "Email (Work)", "Email (Personal)",
    "Phone (Mobile)", "Phone (Work)", "Job Title", "Seniority",
    "Company", "Industry", "City", "State", "Country",
    "Status", "Lead Score", "Deal Value", "Source", "Assigned To",
    "LinkedIn URL", "Notes", "Last Contacted", "Next Follow Up",
    "Created At",
]


def _contact_to_csv_row(c):
    company_name = c.company.company_name if c.company else ""
    industry = c.company.company_industry if c.company else ""
    return [
        c.first_name, c.last_name or "", c.email_work or "", c.email_personal or "",
        c.phone_mobile or "", c.phone_work or "", c.job_title or "", c.seniority_level or "",
        company_name, industry, c.location_city or "", c.location_state or "", c.location_country or "",
        c.lead_status, c.lead_score or "", c.deal_value or "", c.lead_source or "", c.assigned_to or "",
        c.linkedin_url or "", c.notes or "",
        c.last_contacted.strftime("%Y-%m-%d") if c.last_contacted else "",
        c.next_follow_up.strftime("%Y-%m-%d") if c.next_follow_up else "",
        c.created_at.strftime("%Y-%m-%d %H:%M"),
    ]


def _export_contacts_csv(contacts):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_COLUMNS)
    for c in contacts:
        writer.writerow(_contact_to_csv_row(c))
    output.seek(0)
    filename = f"leads-export-{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/leads/export")
def leads_export(db: Session = Depends(get_db)):
    contacts = _active_contacts(db).join(Company, isouter=True).order_by(Contact.created_at.desc()).all()
    return _export_contacts_csv(contacts)


@app.post("/leads/export-selected")
def leads_export_selected(db: Session = Depends(get_db), ids: list[int] = Form(...)):
    contacts = db.query(Contact).join(Company, isouter=True).filter(Contact.id.in_(ids)).all()
    return _export_contacts_csv(contacts)


@app.post("/leads/delete-selected")
def leads_delete_selected(db: Session = Depends(get_db), ids: list[int] = Form(...)):
    # Soft delete: set deleted_at timestamp
    now = datetime.utcnow()
    db.query(Contact).filter(Contact.id.in_(ids), Contact.deleted_at.is_(None)).update(
        {"deleted_at": now}, synchronize_session=False)
    db.commit()
    return RedirectResponse("/leads", status_code=303)


@app.post("/leads/{contact_id}/delete")
def lead_delete(contact_id: int, db: Session = Depends(get_db)):
    contact = db.query(Contact).get(contact_id)
    if not contact:
        raise HTTPException(status_code=404)
    contact.deleted_at = datetime.utcnow()
    db.commit()
    return RedirectResponse("/leads", status_code=303)


# ── Trash (soft-deleted leads) ────────────────────────────────────────────────

@app.get("/leads/trash", response_class=HTMLResponse)
def leads_trash(request: Request, db: Session = Depends(get_db)):
    trashed = (
        db.query(Contact).join(Company, isouter=True)
        .filter(Contact.deleted_at.isnot(None))
        .order_by(Contact.deleted_at.desc())
        .all()
    )
    return templates.TemplateResponse("leads_trash.html", {
        "request": request,
        "settings": settings,
        "user": _get_user(request, db),
        "contacts": trashed,
    })


@app.post("/leads/trash/restore-selected")
def leads_restore_selected(db: Session = Depends(get_db), ids: list[int] = Form(...)):
    db.query(Contact).filter(Contact.id.in_(ids)).update(
        {"deleted_at": None}, synchronize_session=False)
    db.commit()
    return RedirectResponse("/leads/trash", status_code=303)


@app.post("/leads/{contact_id}/restore")
def lead_restore(contact_id: int, db: Session = Depends(get_db)):
    contact = db.query(Contact).get(contact_id)
    if not contact:
        raise HTTPException(status_code=404)
    contact.deleted_at = None
    db.commit()
    return RedirectResponse("/leads/trash", status_code=303)


@app.post("/leads/trash/force-delete-selected")
def leads_force_delete_selected(db: Session = Depends(get_db), ids: list[int] = Form(...)):
    # Permanent delete: remove related records then contacts
    db.query(Meeting).filter(Meeting.contact_id.in_(ids)).delete(synchronize_session=False)
    db.query(NurtureEnrollment).filter(NurtureEnrollment.contact_id.in_(ids)).delete(synchronize_session=False)
    db.query(Proposal).filter(Proposal.contact_id.in_(ids)).delete(synchronize_session=False)
    db.query(Contact).filter(Contact.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    return RedirectResponse("/leads/trash", status_code=303)


@app.post("/leads/{contact_id}/force-delete")
def lead_force_delete(contact_id: int, db: Session = Depends(get_db)):
    contact = db.query(Contact).get(contact_id)
    if not contact:
        raise HTTPException(status_code=404)
    db.query(Meeting).filter(Meeting.contact_id == contact_id).delete()
    db.query(NurtureEnrollment).filter(NurtureEnrollment.contact_id == contact_id).delete()
    db.query(Proposal).filter(Proposal.contact_id == contact_id).delete()
    db.delete(contact)
    db.commit()
    return RedirectResponse("/leads/trash", status_code=303)


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
        "user": _get_user(request, db),
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
            _active_contacts(db)
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
        "user": _get_user(request, db),
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
        contacts = _active_contacts(db).filter(Contact.lead_status == stage).all()
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

import threading as _threading

scraper_results: list[dict] = []
scraper_status: dict = {"running": False, "sources": {}, "total_found": 0, "message": "Idle"}
_scraper_lock = _threading.Lock()


@app.get("/scraper", response_class=HTMLResponse)
def scraper_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("scraper.html", {
        "request": request,
        "settings": settings,
        "user": _get_user(request, db),
        "scraper_status": scraper_status,
        "results": scraper_results,
        "get_source_badge_css": get_source_badge_css,
    })


@app.post("/scraper/start", response_class=HTMLResponse)
def scraper_start(
    request: Request,
    keywords: str = Form(""),
    location: str = Form("Australia"),
    max_results: int = Form(20),
    sources: str = Form("linkedin"),
    linkedin_email: str = Form(""),
    linkedin_password: str = Form(""),
    aca_username: str = Form(""),
    aca_password: str = Form(""),
    ampp_username: str = Form(""),
    ampp_password: str = Form(""),
    tenders_date_from: str = Form(""),
    tenders_date_to: str = Form(""),
    tenders_states: str = Form(""),
    trade_show_events: str = Form(""),
    trade_show_custom_url: str = Form(""),
):
    import threading
    from scraper.search_engine import run_scrape

    scraper_results.clear()
    source_list = [s.strip() for s in sources.split(",") if s.strip()]
    scraper_status.update({"running": True, "sources": {}, "total_found": 0, "message": f"Starting scrape ({len(source_list)} sources)..."})

    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]
    if not keyword_list:
        keyword_list = settings.industry_keywords[:5]

    # Build credentials dict
    credentials = {}
    if linkedin_email:
        credentials["linkedin"] = {"email": linkedin_email, "password": linkedin_password}
    elif settings.linkedin_email:
        credentials["linkedin"] = {"email": settings.linkedin_email, "password": settings.linkedin_password}
    if aca_username:
        credentials["aca"] = {"username": aca_username, "password": aca_password}
    if ampp_username:
        credentials["ampp"] = {"username": ampp_username, "password": ampp_password}

    # Build source configs
    source_configs = {}
    if tenders_date_from or tenders_date_to:
        tender_config = {}
        if tenders_date_from:
            tender_config["date_from"] = tenders_date_from
        if tenders_date_to:
            tender_config["date_to"] = tenders_date_to
        if tenders_states:
            tender_config["states"] = [s.strip() for s in tenders_states.split(",") if s.strip()]
        source_configs["tenders_au"] = tender_config
        source_configs["tenders_nz"] = {"date_from": tender_config.get("date_from", ""), "date_to": tender_config.get("date_to", "")}
    if trade_show_events or trade_show_custom_url:
        ts_config = {}
        if trade_show_events:
            ts_config["events"] = [e.strip() for e in trade_show_events.split(",") if e.strip()]
        if trade_show_custom_url:
            ts_config["event_urls"] = [trade_show_custom_url.strip()]
        source_configs["trade_shows"] = ts_config

    logger.info(f"WEB: Multi-source scrape — sources={source_list}, keywords={keyword_list}, location={location}")

    def _scrape():
        try:
            results, status = run_scrape(source_list, keyword_list, location, max_results, credentials, source_configs)
            with _scraper_lock:
                scraper_results.extend(results)
                scraper_status.update({"running": False, "sources": status.get("sources", {}), "total_found": len(results), "message": f"Complete. Found {len(results)} leads."})
            logger.info(f"WEB: Scrape finished — {len(results)} leads found")
        except Exception as e:
            with _scraper_lock:
                scraper_status.update({"running": False, "total_found": 0, "message": f"Error: {str(e)}"})
            logger.error(f"WEB: Scrape failed — {e}")

    thread = threading.Thread(target=_scrape, daemon=True)
    thread.start()

    return templates.TemplateResponse("partials/scraper_status.html", {
        "request": request,
        "scraper_status": scraper_status,
        "results": scraper_results,
        "get_source_badge_css": get_source_badge_css,
    })


@app.get("/scraper/status", response_class=HTMLResponse)
def scraper_status_check(request: Request):
    return templates.TemplateResponse("partials/scraper_status.html", {
        "request": request,
        "scraper_status": scraper_status,
        "results": scraper_results,
        "get_source_badge_css": get_source_badge_css,
    })


@app.post("/scraper/cancel", response_class=HTMLResponse)
def scraper_cancel(request: Request):
    from scraper.search_engine import cancel_scrape
    cancel_scrape()
    scraper_status.update({"running": False, "message": "Cancelled by user"})
    return templates.TemplateResponse("partials/scraper_status.html", {
        "request": request,
        "scraper_status": scraper_status,
        "results": scraper_results,
        "get_source_badge_css": get_source_badge_css,
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
    if not existing and result.get("first_name") and result.get("last_name") and result.get("company_name"):
        existing = db.query(Contact).filter(
            Contact.first_name == result["first_name"],
            Contact.last_name == result["last_name"],
            Contact.company.has(Company.company_name == result["company_name"]),
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
                company_domain=result.get("company_domain"),
                company_industry=result.get("company_industry", ""),
                company_location=result.get("company_location", ""),
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
        lead_source=result.get("source_name", "Unknown"),
        source_url=result.get("source_url"),
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
        "source_name": result.get("source_name", "Unknown"),
        "source_badge_css": get_source_badge_css(result.get("source_name", "")),
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
        "scraper_status": {"running": False, "total_found": scraper_status.get("total_found", 0), "message": msg},
        "results": scraper_results,
        "added_indices": indices,
        "get_source_badge_css": get_source_badge_css,
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
    contacts = _active_contacts(db).order_by(Contact.first_name).all()

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
        "user": _get_user(request, db),
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
    contacts = _active_contacts(db).order_by(Contact.first_name).all()

    return templates.TemplateResponse("nurture.html", {
        "request": request,
        "settings": settings,
        "user": _get_user(request, db),
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
def nurture_preview(
    request: Request,
    enrollment_id: int,
    step: int = Query(None),
    db: Session = Depends(get_db),
):
    enrollment = db.query(NurtureEnrollment).get(enrollment_id)
    if not enrollment:
        raise HTTPException(status_code=404)

    seq = enrollment.sequence
    contact = enrollment.contact
    company = contact.company
    total_steps = len(seq.steps)

    # Allow browsing any step; default to current_step
    step_idx = step if step is not None else enrollment.current_step
    step_idx = max(0, min(step_idx, total_steps - 1))

    step_data = seq.steps[step_idx]
    body = step_data["body_template"].format(
        first_name=contact.first_name,
        last_name=contact.last_name or "",
        company_name=company.company_name if company else "",
        company_industry=company.company_industry if company else "",
        location_state=contact.location_state or "",
    )

    return templates.TemplateResponse("partials/nurture_preview.html", {
        "request": request,
        "step": step_data,
        "body": body,
        "enrollment": enrollment,
        "step_index": step_idx,
        "step_number": step_idx + 1,
        "total_steps": total_steps,
        "current_step": enrollment.current_step,
    })


@app.post("/nurture/enrollments/{enrollment_id}/advance")
def nurture_advance(request: Request, enrollment_id: int, db: Session = Depends(get_db)):
    enrollment = db.query(NurtureEnrollment).get(enrollment_id)
    if not enrollment:
        raise HTTPException(status_code=404)

    if enrollment.current_step + 1 >= len(enrollment.sequence.steps):
        enrollment.status = "Completed"
    else:
        enrollment.current_step += 1
    db.commit()

    # Redirect back to the referring page (lead detail or nurture)
    referer = request.headers.get("referer", "")
    if "/leads/" in referer:
        return RedirectResponse(referer, status_code=303)
    return RedirectResponse("/nurture", status_code=303)


# ── Proposals ──────────────────────────────────────────────────────────────────

@app.get("/proposals", response_class=HTMLResponse)
def proposals_page(request: Request, db: Session = Depends(get_db)):
    proposals = db.query(Proposal).order_by(Proposal.created_at.desc()).all()
    contacts = _active_contacts(db).order_by(Contact.first_name).all()

    return templates.TemplateResponse("proposals.html", {
        "request": request,
        "settings": settings,
        "user": _get_user(request, db),
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


@app.get("/proposals/{proposal_id}/preview", response_class=HTMLResponse)
def proposals_preview(request: Request, proposal_id: int, db: Session = Depends(get_db)):
    """Render the proposal as HTML in the browser (same content as the PDF)."""
    proposal = db.query(Proposal).get(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404)

    contact = proposal.contact
    company = contact.company if contact else None

    from proposals.pdf_generator import proposal_env
    template = proposal_env.get_template("proposal.html")
    html_content = template.render(
        company=settings.company_name,
        website=settings.company_website,
        contact_name=f"{contact.first_name} {contact.last_name or ''}".strip(),
        company_name=company.company_name if company else "",
        products=proposal.products,
        total_price=proposal.pricing,
        notes="",
        proposal_number=f"COR-{proposal.created_at.strftime('%Y%m%d%H%M%S')}",
        date=proposal.created_at.strftime("%d %B %Y"),
        differentiators=settings.key_differentiators,
    )
    return HTMLResponse(html_content)


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
