# MasterSales

A local sales activation platform built for **Corrizon Australasia** — a steel treatment company targeting AU/NZ markets. Replicates core Sales Navigator and Apollo.io functionality without third-party SaaS dependencies.

## Features

### Lead Sourcing
- LinkedIn people search with Playwright headless browser
- Geo-filtered for Australia and New Zealand (state-level filtering)
- Multi-keyword search strategy with deduplication
- Bulk add to leads with duplicate detection
- Demo data mode when LinkedIn credentials are not configured

### Lead Management
- Full contact database with company associations
- Search, filter by status, and sort leads
- Lead scoring (1-100) and deal value tracking
- Status workflow: New > Contacted > Qualified > Proposal > Negotiation > Won/Lost
- Detailed lead profiles with activity timeline

### Pipeline (Kanban)
- Drag-and-drop Kanban board for deal stages
- Pipeline value statistics per stage
- Visual deal tracking with conversion metrics

### Meeting Scheduler
- Create and manage meetings linked to contacts
- Calendar view of upcoming meetings
- Meeting status tracking (Scheduled, Completed, Cancelled, No-show)

### Nurture Sequences
- Multi-step email sequences with template variables
- Enroll contacts into sequences
- Preview any step with personalized content
- Step-by-step navigation (prev/next + dot indicators)
- Advance through sequence steps

### Proposals
- Branded PDF proposal generation (WeasyPrint)
- HTML email proposal generation
- Product/service line items with quantities and pricing
- In-browser proposal preview (same layout as PDF)
- Proposal status tracking (Draft, Sent, Viewed, Accepted, Declined)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | [FastAPI](https://fastapi.tiangolo.com/) |
| Database | SQLite + [SQLAlchemy](https://www.sqlalchemy.org/) 2.0 |
| Templates | [Jinja2](https://jinja.palletsprojects.com/) |
| Frontend | [Tailwind CSS](https://tailwindcss.com/) (CDN) + [HTMX](https://htmx.org/) + [Alpine.js](https://alpinejs.dev/) |
| PDF Generation | [WeasyPrint](https://weasyprint.org/) |
| LinkedIn Scraping | [Playwright](https://playwright.dev/python/) (Chromium) |
| Kanban DnD | [SortableJS](https://sortablejs.github.io/Sortable/) |
| Config | [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) with `.env` |
| Testing | [pytest](https://docs.pytest.org/) + FastAPI TestClient |

## Project Structure

```
mastersales/
├── app.py                          # FastAPI application and routes
├── config.py                       # Pydantic settings (ICP, products, company info)
├── requirements.txt
├── .env.example                    # Environment template
│
├── database/
│   ├── db.py                       # SQLAlchemy engine and session
│   ├── models.py                   # ORM models (Company, Contact, Meeting, etc.)
│   └── seed.py                     # Demo data seeder
│
├── scraper/
│   ├── linkedin.py                 # Playwright-based LinkedIn scraper
│   ├── search_engine.py            # Search orchestrator + demo data generator
│   └── web_enricher.py             # Domain/email enrichment utilities
│
├── scheduler/
│   └── meeting.py                  # Meeting creation and query helpers
│
├── pipeline/
│   ├── deal_tracker.py             # Pipeline statistics and deal tracking
│   └── nurture_engine.py           # Nurture sequence step rendering
│
├── proposals/
│   ├── pdf_generator.py            # WeasyPrint PDF generation
│   ├── email_generator.py          # HTML email rendering
│   └── templates/
│       ├── proposal.html           # Branded PDF/preview template
│       └── email.html              # Email proposal template
│
├── templates/                      # Jinja2 page templates
│   ├── base.html                   # Layout with sidebar navigation
│   ├── dashboard.html
│   ├── leads.html / lead_detail.html
│   ├── scraper.html
│   ├── pipeline.html
│   ├── scheduler.html
│   ├── nurture.html
│   ├── proposals.html
│   └── partials/                   # HTMX partial templates
│       ├── leads_table_body.html
│       ├── scraper_status.html
│       ├── scraper_row_added.html
│       ├── nurture_preview.html
│       ├── pipeline_stats.html
│       └── lead_status_badge.html
│
├── static/
│   ├── css/style.css
│   └── js/app.js                   # HTMX config, Kanban init, Alpine stores
│
├── tests/                          # pytest test suite (30 tests)
│   ├── test_app.py
│   ├── test_models.py
│   ├── test_meeting.py
│   ├── test_nurture.py
│   ├── test_proposals.py
│   ├── test_enricher.py
│   └── test_seed.py
│
└── docs/plans/                     # Design and implementation documents
```

## Getting Started

### Prerequisites

- Python 3.11+
- System dependencies for WeasyPrint (PDF generation):

```bash
# Ubuntu/Debian
sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi-dev

# macOS
brew install pango
```

### Installation

```bash
# Clone the repository
git clone https://github.com/Evan-Kun/mastersales.git
cd mastersales

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser (for LinkedIn scraping)
playwright install chromium
```

### Configuration

```bash
# Copy environment template
cp .env.example .env
```

Edit `.env` with your settings:

```env
# LinkedIn credentials (optional — leave empty for demo mode)
LINKEDIN_EMAIL=
LINKEDIN_PASSWORD=

# Scraper rate limiting
SCRAPE_DELAY_MIN=2.0
SCRAPE_DELAY_MAX=5.0

# App settings
DEBUG=true
DATABASE_URL=sqlite:///mastersales.db
```

### Run the Application

```bash
source venv/bin/activate
uvicorn app:app --reload --port 8899
```

Open **http://127.0.0.1:8899** in your browser.

On first launch, the database is automatically created and seeded with demo data (Australian/NZ steel fabrication companies, contacts, nurture sequences, and sample proposals).

### Run Tests

```bash
source venv/bin/activate
pytest tests/ -v
```

## Usage Guide

### Lead Sourcing (Scraper)

1. Navigate to **Lead Sourcing** in the sidebar
2. Enter industry keywords (e.g., `steel, corrosion, fabrication`)
3. Select a location filter (AU+NZ, specific states, or NZ only)
4. Click **Start Scraping**
5. Results appear in a table with checkboxes
6. Use **Select All** + **Add Selected to Leads** for bulk import
7. Duplicates are detected by LinkedIn URL and name — shown with amber "Already exists" badge

**Demo mode**: If no LinkedIn credentials are set in `.env`, the scraper generates realistic demo data using seeded random names, titles, and companies.

**Live mode**: With LinkedIn credentials configured, Playwright logs into LinkedIn, runs people searches with geo-filtering, and extracts results from the rendered DOM.

### Proposals

1. Navigate to **Proposals**
2. Select a contact, check products, set quantities
3. Click **Generate Proposal**
4. Three outputs are created:
   - **Preview Proposal** — opens the branded proposal in browser
   - **Download PDF** — downloads the A4 PDF file
   - **Preview Email** — opens the email-formatted version

### Nurture Sequences

1. Navigate to **Nurture** to see all sequences
2. Enroll a contact into a sequence
3. Click **Preview All Steps** to browse through each email step
4. Use prev/next buttons or dot indicators to navigate steps
5. Click **Advance** to progress to the next step

## API Routes

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Dashboard with KPIs |
| `GET` | `/leads` | Leads list with search/filter |
| `GET` | `/leads/{id}` | Lead detail with activity timeline |
| `POST` | `/leads/{id}/update` | Update lead status, score, notes |
| `GET` | `/scraper` | Scraper search form |
| `POST` | `/scraper/start` | Launch scrape job |
| `POST` | `/scraper/add/{index}` | Add single scrape result to leads |
| `POST` | `/scraper/add-bulk` | Bulk add scrape results to leads |
| `GET` | `/pipeline` | Kanban pipeline board |
| `POST` | `/pipeline/move` | Move deal to new stage |
| `GET` | `/scheduler` | Meeting scheduler |
| `POST` | `/scheduler/create` | Create new meeting |
| `GET` | `/nurture` | Nurture sequences and enrollments |
| `POST` | `/nurture/enroll` | Enroll contact in sequence |
| `GET` | `/nurture/enrollments/{id}/preview?step=N` | Preview any step email |
| `POST` | `/nurture/enrollments/{id}/advance` | Advance enrollment step |
| `GET` | `/proposals` | Proposals list |
| `POST` | `/proposals/create` | Generate new proposal |
| `GET` | `/proposals/{id}/preview` | Browser preview of proposal |
| `GET` | `/proposals/{id}/pdf` | Download proposal PDF |
| `GET` | `/proposals/{id}/email-preview` | Preview email version |
| `POST` | `/proposals/{id}/send` | Mark proposal as sent |

## Data Models

- **Company** — name, industry, website, size, revenue, ABN, location
- **Contact** — name, title, email, phone, LinkedIn URL, lead status, score, deal value
- **Meeting** — linked to contact, time, duration, location, status, notes
- **NurtureSequence** — name, description, steps (JSON array of subject/body/day_offset)
- **NurtureEnrollment** — links contact to sequence, tracks current step and status
- **Proposal** — linked to contact, products (JSON), pricing, PDF path, email HTML, status

## LinkedIn Scraper Details

The scraper uses Playwright to automate a headless Chromium browser:

1. **Login** — multi-selector fallback for LinkedIn's changing login page
2. **Search** — keywords are split into individual queries (LinkedIn returns few results with many keywords combined)
3. **Geo-filtering** — uses LinkedIn `geoUrn` IDs for AU/NZ states
4. **DOM extraction** — reads `data-view-name="people-search-result"` cards for name, headline, location, and profile URL
5. **API supplementation** — intercepts Voyager API responses to fill in missing fields
6. **Rate limiting** — random delays between requests (configurable via `SCRAPE_DELAY_MIN/MAX`)
7. **Debug output** — saves screenshots and page HTML to `output/` for troubleshooting

## License

This project is for internal demo and development purposes.
