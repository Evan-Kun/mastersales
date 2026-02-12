# Master Sales Activation Platform — Design Document

**Date:** 2026-02-13
**Project:** MasterSales
**Company:** Corrizon Australasia Pty Ltd
**Purpose:** Local demo of a sales activation platform replicating Apollo.io/Sales Navigator functionality

---

## Overview

A locally-run sales activation platform for Corrizon Australasia to demo lead generation,
pipeline management, proposal generation, and deal closure for their anti-corrosion steel
treatment system targeting steel fabrication companies in Australia & New Zealand.

**Pillars implemented:**
1. Intelligent Lead Sourcing (LinkedIn web scraper)
2. Smart Meeting Scheduling (local calendar)
3. Dynamic Lead Nurturing (email sequence engine)
4. Automated Proposals (PDF + HTML email generation)
5. Intelligent Deal Closure (Kanban pipeline tracker)

**Pillars skipped:** AI chatbots, automated lead capture/forms, predictive lead scoring, instant follow-up.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.11+ / FastAPI |
| Frontend | Jinja2 templates + HTMX + Alpine.js |
| Database | SQLite (via SQLAlchemy) |
| Scraper | Playwright (headless Chromium) |
| PDF generation | WeasyPrint or ReportLab |
| CSS | Tailwind CSS (CDN) |
| Run command | `python app.py` → opens browser |

---

## Data Model

### Contact Table

| Field | Type | Notes |
|-------|------|-------|
| id | integer PK | Auto-increment |
| first_name | text | |
| last_name | text | |
| job_title | text | |
| seniority_level | text | Owner/C-Suite/VP/Director/Manager/Staff |
| email_work | text | |
| email_personal | text | |
| phone_mobile | text | |
| phone_work | text | |
| linkedin_url | text | Unique |
| location_city | text | |
| location_state | text | WA, Vic, etc. |
| location_country | text | AU/NZ |
| years_in_role | integer | |
| profile_summary | text | |
| lead_status | text | New/Contacted/Qualified/Proposal/Negotiation/Won/Lost |
| lead_score | integer | 1-100 manual scoring |
| lead_source | text | LinkedIn/Web/CSV |
| assigned_to | text | Sales rep name |
| notes | text | |
| last_contacted | datetime | |
| next_follow_up | datetime | |
| deal_value | decimal | $500-$15,000 |
| created_at | datetime | |
| updated_at | datetime | |
| company_id | integer FK | Links to Company |

### Company Table

| Field | Type | Notes |
|-------|------|-------|
| id | integer PK | |
| company_name | text | |
| company_website | text | |
| company_industry | text | |
| company_size | text | Employee range |
| company_revenue | text | Revenue band |
| company_founded | integer | Year |
| company_description | text | |
| company_linkedin_url | text | Unique |
| company_location | text | HQ address |
| company_keywords | text | ICP match tags (comma-separated) |
| abn | text | Australian Business Number |
| created_at | datetime | |
| updated_at | datetime | |

### Meeting Table

| Field | Type | Notes |
|-------|------|-------|
| id | integer PK | |
| contact_id | integer FK | |
| title | text | Meeting subject |
| agenda | text | |
| meeting_time | datetime | |
| duration_minutes | integer | Default 30 |
| location | text | Address or video link |
| status | text | Scheduled/Completed/Cancelled |
| notes | text | Post-meeting notes |
| created_at | datetime | |

### NurtureSequence Table

| Field | Type | Notes |
|-------|------|-------|
| id | integer PK | |
| name | text | e.g. "Steel Fabricator Intro" |
| description | text | |
| steps | JSON | Array of {day_offset, subject, body_template} |
| created_at | datetime | |

### NurtureEnrollment Table

| Field | Type | Notes |
|-------|------|-------|
| id | integer PK | |
| contact_id | integer FK | |
| sequence_id | integer FK | |
| current_step | integer | 0-based index |
| enrolled_at | datetime | |
| status | text | Active/Paused/Completed |

### Proposal Table

| Field | Type | Notes |
|-------|------|-------|
| id | integer PK | |
| contact_id | integer FK | |
| products | JSON | Array of selected products/services |
| pricing | decimal | Total proposal value |
| pdf_path | text | Path to generated PDF |
| email_html | text | Generated email HTML |
| status | text | Draft/Sent/Viewed/Accepted/Declined |
| created_at | datetime | |
| sent_at | datetime | |

---

## Architecture

```
mastersales/
├── app.py                    # FastAPI entry point
├── config.py                 # ICP config, Corrizon details, scraper settings
├── requirements.txt
├── database/
│   ├── models.py             # SQLAlchemy ORM models
│   ├── db.py                 # SQLite engine & session factory
│   └── seed.py               # Optional demo seed data
├── scraper/
│   ├── linkedin.py           # Playwright-based LinkedIn scraper
│   ├── web_enricher.py       # ABN lookup, website metadata enrichment
│   └── search_engine.py      # Orchestrates ICP-based searches
├── pipeline/
│   ├── deal_tracker.py       # Deal stage transitions, pipeline stats
│   └── nurture_engine.py     # Nurture sequence management & scheduling
├── proposals/
│   ├── pdf_generator.py      # WeasyPrint PDF generation
│   ├── email_generator.py    # HTML email rendering
│   └── templates/
│       ├── proposal.html     # PDF proposal template
│       └── email.html        # Email proposal template
├── scheduler/
│   └── meeting.py            # Meeting CRUD & calendar logic
├── templates/                # Jinja2 UI templates
│   ├── base.html             # Layout with nav, Tailwind, HTMX
│   ├── dashboard.html        # Summary cards, pipeline snapshot
│   ├── leads.html            # Full lead table with search/filter
│   ├── lead_detail.html      # Single lead profile + activity
│   ├── pipeline.html         # Kanban board (drag-and-drop)
│   ├── scraper.html          # Lead sourcing controls + live results
│   ├── proposals.html        # Proposal generator
│   ├── scheduler.html        # Meeting calendar
│   └── nurture.html          # Nurture sequences management
├── static/
│   ├── css/style.css
│   ├── js/app.js             # HTMX config + Alpine.js components
│   └── img/                  # Corrizon logo & branding
└── output/
    └── proposals/            # Generated PDF files stored here
```

---

## UI Pages

### 1. Dashboard
- Summary cards: Total Leads, Active Deals, Proposals Sent, Meetings This Week
- Mini Kanban pipeline snapshot
- Recent activity feed
- ICP match statistics

### 2. Lead Sourcing (Scraper)
- ICP search panel pre-loaded with Corrizon's criteria
- Keywords: steel, corrosion, fabrication, mining, engineering, shipbuilding, zinc, coating, rust
- Locations: WA, Vic (primary), all AU/NZ
- Live scraping progress via HTMX polling
- Results table with one-click "Add to Pipeline"

### 3. Leads Table
- Full CRM view: search, filter, sort across all fields
- Inline editing for status, score, notes
- Bulk actions (assign rep, change status)
- Click-through to lead detail page

### 4. Pipeline Board
- Kanban: New → Contacted → Qualified → Proposal Sent → Negotiation → Won → Lost
- Drag-and-drop via SortableJS + HTMX
- Deal cards: company, value, contact, days in stage
- Filter by rep, date, value range

### 5. Meeting Scheduler
- Week/month calendar view
- Create meetings linked to leads
- Upcoming meetings list

### 6. Nurture Sequences
- Create/edit nurture sequences (timed email drafts)
- Enroll leads in sequences
- Track progress through sequence steps
- Preview queued drafts

### 7. Proposal Generator
- Select lead → auto-populate company data
- Choose Corrizon products/services
- Set pricing
- Preview PDF and email versions
- Download PDF / copy email HTML

---

## LinkedIn Scraping Approach

- Uses Playwright headless Chromium browser
- Requires user's LinkedIn credentials (stored locally in config, never transmitted)
- Searches LinkedIn by ICP keywords + location filters
- Extracts: name, title, company, location, profile URL, summary
- Enriches with company data from company pages
- Rate-limited with random delays (2-5 seconds between actions) to mimic human behavior
- Respects LinkedIn session limits
- All data stored locally in SQLite

---

## ICP Configuration (Pre-loaded)

```python
ICP_CONFIG = {
    "company_name": "Corrizon Australasia Pty Ltd",
    "website": "www.corrizon.com.au",
    "target_countries": ["AU", "NZ"],
    "priority_states": ["WA", "VIC"],
    "industry_keywords": [
        "steel", "corrosion", "rust", "protection", "coating",
        "zinc", "paint", "undercoat", "treatment", "maintenance",
        "salt", "mining", "engineering", "shipbuilding", "machinery",
        "fabrication", "application"
    ],
    "deal_size_range": {"min": 500, "max": 15000},
    "sales_cycle": "monthly",
    "key_differentiators": [
        "Environmentally friendly",
        "Water based",
        "Minimal VOCs",
        "Cost saving",
        "Time saving",
        "Better schedule control",
        "Easy application",
        "Reduced preparation",
        "Simple clean up",
        "Superior protection"
    ]
}
```

---

## Sources

- [Apollo.io Data Overview](https://knowledge.apollo.io/hc/en-us/articles/19331318468621-Apollo-Data-Overview)
- [LinkedIn Sales Navigator](https://business.linkedin.com/sales-solutions/sales-navigator)
