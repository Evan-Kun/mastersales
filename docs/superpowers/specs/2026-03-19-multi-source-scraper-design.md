# Multi-Source Scraper — Design Specification

**Date:** 2026-03-19
**Status:** Approved
**Scope:** Expand MasterSales scraper from LinkedIn-only to 6 industry-specific sources

---

## 1. Problem

The current scraper only targets LinkedIn People Search. To build a comprehensive corrosion-industry lead database, we need to scrape multiple industry-specific sources: association directories, government tender portals, and trade show exhibitor lists.

## 2. Architecture

### 2.1 Pluggable Source System

Each source is a Python class implementing `BaseScraper`. The orchestrator instantiates selected scrapers, runs them in parallel threads, and merges results.

```
scraper/
├── base.py              # BaseScraper interface + ScraperResult schema
├── linkedin.py          # Existing (refactored to implement BaseScraper)
├── aca.py               # Australasian Corrosion Association
├── ampp.py              # AMPP community directory
├── tenders_au.py        # AusTender + state portals (QLD, NSW, VIC, WA)
├── tenders_nz.py        # GETS (NZ Government Electronic Tenders)
├── trade_shows.py       # Hardcoded events + generic URL scraper
├── search_engine.py     # Orchestrator (rewritten)
└── web_enricher.py      # Existing
```

### 2.2 BaseScraper Interface

```python
# scraper/base.py

class ScraperConfig(TypedDict, total=False):
    """Unified config passed to each scraper's scrape() method."""
    keywords: list[str]              # Industry keywords
    location: str                    # Location filter
    max_results: int                 # Per-source cap
    credentials: dict[str, str]      # Source-specific creds (e.g. {"email": "...", "password": "..."})
    date_from: str                   # For tenders: ISO date string
    date_to: str                     # For tenders: ISO date string
    states: list[str]                # For AU tenders: state filter
    event_urls: list[str]            # For trade shows: custom URLs
    events: list[str]                # For trade shows: hardcoded event slugs

class ScraperResult(TypedDict):
    first_name: str                  # Required — core identifier
    last_name: str                   # Required — core identifier
    job_title: str | None
    company_name: str                # Required — core identifier, used in dedup key
    company_domain: str | None       # e.g. "bhp.com"
    linkedin_url: str | None
    location_city: str | None
    location_state: str | None
    location_country: str | None     # "AU" or "NZ"
    source_url: str | None           # page URL where lead was found
    source_name: str                 # "LinkedIn", "ACA", "AMPP", etc.

class BaseScraper(ABC):
    name: str                        # Display name for UI
    slug: str                        # Registry key: "linkedin", "aca", etc.
    requires_auth: bool              # Whether credentials are needed
    credential_fields: list[dict]    # Dynamic form fields for UI
    uses_browser: bool               # Whether this scraper needs Playwright (for concurrency limiting)

    @abstractmethod
    def scrape(self, config: ScraperConfig) -> list[ScraperResult]:
        """Run the scrape. Returns results with all required fields populated."""
        ...

    @abstractmethod
    def generate_demo_results(self, config: ScraperConfig) -> list[ScraperResult]:
        """Generate deterministic demo data when live scraping unavailable."""
        ...

    def validate_credentials(self, credentials: dict) -> bool:
        return True
```

### 2.3 Source Registry

```python
SCRAPERS = {
    "linkedin": LinkedInScraper,
    "aca": ACAScraper,
    "ampp": AMPPScraper,
    "tenders_au": AusTenderScraper,
    "tenders_nz": GETSScraper,
    "trade_shows": TradeShowScraper,
}
```

## 3. Target Sources

### 3.1 LinkedIn (refactor of existing)

- **Target:** linkedin.com People Search
- **Auth:** Email + Password (required for live mode)
- **Existing logic preserved:** login, query building, dual extraction (DOM + API intercept), geo-filtering, rate limiting
- **Changes:** Wrap in BaseScraper interface, add `source_url` and `source_name` to output

### 3.2 ACA — Australasian Corrosion Association

- **Target:** corrosion.com.au
- **Auth:** Optional — try public pages first (event attendees, committee lists, technical paper authors). If member directory is gated, prompt for ACA login credentials.
- **Extracts:** Name, company, role/title from member cards or tables
- **source_name:** "ACA"

### 3.3 AMPP — Association for Materials Protection and Performance

- **Target:** ampp.org (AU chapter preferred)
- **Auth:** Optional — public first (conference speakers, chapter member lists), auth fallback
- **Note:** NACE merged into AMPP in 2021. This scraper covers both.
- **source_name:** "AMPP"

### 3.4 Australian Government Tender Portals

- **Targets:**
  - AusTender (tenders.gov.au) — federal
  - QTenders (qtenders.epw.qld.gov.au) — QLD
  - eTendering (tenders.nsw.gov.au) — NSW
  - Tenders VIC (tenders.vic.gov.au) — VIC
  - GEMS (gem.wa.gov.au) — WA
- **Auth:** None (all public)
- **Extra config:** Date range filter (default: last 12 months), state checkboxes
- **Extracts:** Company name, contact officer name, ABN, company domain, contract description
- **Note:** Company-heavy, contact-light. Some tenders list a contact officer name.
- **source_name:** "AusTender", "QTenders", "eTendering", "Tenders VIC", "GEMS WA"

### 3.5 GETS — NZ Government Electronic Tenders

- **Target:** gets.govt.nz
- **Auth:** None (public)
- **Extra config:** Date range filter (default: last 12 months)
- **Same extraction pattern as AU tenders**
- **source_name:** "GETS"

### 3.6 Trade Shows

- **Hardcoded events** (scraped by known URL patterns):
  - Australasian Corrosion Conference (ACA annual)
  - Austmine conference
  - AMPP annual conference (AU chapter)
  - Steel Australia Conference
- **Generic mode:** User pastes any exhibitor page URL. Scraper attempts extraction from common HTML structures (tables, card grids, definition lists). If extraction finds 0 results from the page, it returns an empty list with a warning log — no error, no demo fallback. The user can try a different URL.
- **Extra config:** Event URL text input for generic mode
- **source_name:** "Trade Show: {event_name}" (for hardcoded), "Trade Show: Custom" (for generic URLs)

## 4. Database Changes

### 4.1 Contact Model

Add one field:

```python
source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
```

Existing `lead_source` field maps to `source_name` from ScraperResult.

### 4.2 Company Model

Add one field:

```python
company_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
```

### 4.3 linkedin_url Constraint

The existing `linkedin_url` column has `unique=True`. Since most non-LinkedIn sources produce `linkedin_url = None`, the UNIQUE constraint must be changed to allow multiple NULLs. Change to a conditional unique index or simply drop the unique constraint and handle dedup in application logic.

### 4.4 lead_source Field Width

Widen `lead_source` from `String(50)` to `String(100)` to accommodate longer source names like `"Trade Show: Australasian Corrosion Conference"`.

### 4.5 Deduplication Update

**Two dedup layers:**

1. **Orchestrator cross-source dedup** (in `search_engine.py`, before results reach the UI):
   - Key: `(lower(first_name), lower(last_name), lower(company_name))`
   - Merge strategy: when same person found in multiple sources, keep the record with more non-None fields. Store all source_names as comma-separated in a `sources` field on the merged result for display.

2. **DB-save dedup** (in `app.py` `_add_scraper_result_to_db`):
   - Current: checks `linkedin_url` OR `(first_name + last_name)`
   - New: checks `linkedin_url` (if non-None) OR `(first_name + last_name + company_name)`
   - Both layers must use the same key to stay consistent.

## 5. Orchestrator Design

### 5.1 Updated `run_scrape()` Signature

```python
def run_scrape(
    sources: list[str],              # ["linkedin", "aca", "tenders_au"]
    keywords: list[str],
    location: str,
    max_results: int,
    credentials: dict[str, dict],    # {"linkedin": {"email": "...", "password": "..."}}
    source_configs: dict,            # {"tenders_au": {"date_from": "...", "date_to": "..."}}
) -> list[ScraperResult]:
```

### 5.2 Execution Flow

1. Instantiate selected scrapers from registry
2. **Concurrency limit**: max 2 browser-based scrapers (`uses_browser=True`) run simultaneously to avoid memory exhaustion (~200-500MB per Chromium instance). HTTP-only scrapers (tenders) run without limit. Use a `threading.Semaphore(2)` for browser slots.
3. **Thread safety**: all writes to `scraper_status` and `scraper_results` go through a `threading.Lock`.
4. **Cancellation**: a `threading.Event` (`cancel_event`) is checked between pages/requests. Setting it causes all running scrapers to exit gracefully and return partial results. UI gets a "Cancel" button that POSTs to `/scraper/cancel`.
5. `max_results` is **per-source** — if user requests 20 with 3 sources, each source returns up to 20 (max ~60 pre-dedup).
6. Run each in its own daemon thread (parallel, subject to browser semaphore)
7. Update `scraper_status` per source as each completes:
   ```python
   scraper_status = {
       "running": True,
       "sources": {
           "linkedin": {"status": "running", "found": 0},
           "aca": {"status": "complete", "found": 12},
           "tenders_au": {"status": "error", "message": "Timeout"},
       },
       "total_found": 12,
   }
   ```
8. Cross-source dedup after all sources finish: merge by `(first_name, last_name, company_name)`. If same person in multiple sources, keep the richer record and note both sources.
9. Return merged list

## 6. UI Design

### 6.1 Layout Structure

```
┌─────────────────────────────────────────────────────────────┐
│  Lead Sourcing                                              │
│  Multi-source prospect discovery                            │
├─────────────────────────────────────────────────────────────┤
│  Shared Controls: Keywords, Location, Max Results           │
│                                                             │
│  Tab bar: (LinkedIn) (ACA) (AMPP) (AU Tenders) (NZ) (Shows)│
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Source-specific config panel (per active tab)        │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  Source checkboxes: ☑ LinkedIn  ☑ ACA  ☐ AMPP  ...         │
│  [▶ Scrape N Sources]                                      │
├─────────────────────────────────────────────────────────────┤
│  Per-source status bar during scraping                      │
├─────────────────────────────────────────────────────────────┤
│  Results table with Source column + filter dropdown         │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Design System

**Aesthetic:** Industrial operations console. Clean, information-dense, purposeful.

**Existing tokens preserved:** Navy (#1e3a5f), amber accent, white cards, rounded-xl, gray-50 bg.

**Source color badges:**

| Source | Color | CSS |
|--------|-------|-----|
| LinkedIn | Sky blue | `bg-sky-100 text-sky-700` |
| ACA | Emerald | `bg-emerald-100 text-emerald-700` |
| AMPP | Orange | `bg-orange-100 text-orange-700` |
| AU Tenders | Violet | `bg-violet-100 text-violet-700` |
| NZ Tenders | Indigo | `bg-indigo-100 text-indigo-700` |
| Trade Shows | Amber | `bg-amber-100 text-amber-700` |

### 6.3 Tab Design

Horizontal pill tabs. Each pill shows source name + status dot:
- Gray dot: idle/unconfigured
- Green dot: credentials configured
- Blue pulsing dot: currently scraping

Active tab gets navy underline + elevated config panel below.

### 6.4 Per-Tab Controls

| Tab | Controls |
|-----|----------|
| LinkedIn | Email + Password inputs (localStorage) |
| ACA | Username + Password inputs (localStorage, optional) |
| AMPP | Username + Password inputs (localStorage, optional) |
| AU Tenders | Date range picker (default: last 12 months), state checkboxes |
| NZ Tenders | Date range picker (default: last 12 months) |
| Trade Shows | Checkboxes for hardcoded events + "Custom URL" text input |

### 6.5 Results Table

Columns: `☐ | # | Name | Title | Company | Location | Source | Action`

- Source column: colored dot + 3-4 letter abbreviation (compact, scannable)
- Source filter dropdown above table: "All Sources", "LinkedIn only", "ACA only", etc.
- Source URL: hover tooltip or small link icon on the source badge

### 6.6 Credential Storage

All credentials stored in browser localStorage only. Same security model as current LinkedIn credentials. Each source has its own localStorage keys (e.g., `aca_username`, `aca_password`, `aca_remember`).

## 7. Error Handling

### 7.1 Per-Source Isolation

If one source fails, others continue unaffected. Each source reports independently.

| Scenario | Behavior |
|----------|----------|
| Playwright not installed | Browser-based scrapers fall back to demo mode |
| Login fails (bad creds) | That source returns error, others continue |
| CAPTCHA/checkpoint | Source stops, logs screenshot, others continue |
| Timeout | Source retries 2x, then reports error with partial results |
| Empty results | Source reports "0 found" (not error) |
| Rate limited | Source backs off, logs warning, returns partial |

### 7.2 Demo Mode

Each scraper has its own `generate_demo_results()` with source-appropriate fake data:
- LinkedIn: person-focused (existing pattern, seeded RNG)
- ACA/AMPP: member-style records with association titles
- Tenders: company-heavy records with ABN, contract descriptions
- Trade shows: exhibitor records with booth info

Demo activates when: no credentials for auth-gated sources, or Playwright unavailable.

UI shows a small "DEMO" badge on demo results.

## 8. Scraper Output Fields

| Field | Required? | Notes |
|-------|-----------|-------|
| first_name | Required | Core identifier |
| last_name | Required | Core identifier |
| company_name | Required | Core identifier |
| company_domain | Optional | Bare domain for enrichment (e.g. "bhp.com") |
| job_title | Optional | Pass through to CRM if captured |
| linkedin_url | Optional | Only from LinkedIn source |
| location_city | Optional | Geo filtering |
| location_state | Optional | Geo filtering |
| location_country | Optional | "AU" or "NZ" |
| source_url | Recommended | Audit trail — URL where lead was found |
| source_name | Required | Which scraper produced this result |

## 9. Security

- All credentials stored in browser `localStorage` only — never persisted server-side.
- Credentials travel as form POST fields over the network. **HTTPS is required** for any non-localhost deployment.
- Each source has isolated credential keys in localStorage (e.g., `aca_username`, `aca_password`).
- The "Remember" checkbox per source controls whether localStorage persists across sessions.
- The server does not log or store credentials. They are passed directly to the scraper and discarded after the scrape completes.

## 10. Tech Stack

No new dependencies beyond what's already used:
- **Playwright** (existing) for browser-based scraping (LinkedIn, ACA, AMPP, trade shows)
- **HTMX** (existing) for async UI updates
- **Alpine.js** (existing) for tab state, credential management
- **Tailwind CSS** (existing) for styling
- **requests/httpx** — tender portals may use simple HTTP GET (no browser needed) if their pages are server-rendered. Fall back to Playwright if JS-rendered. Mark `uses_browser` accordingly.

## 11. Files to Create/Modify

### New Files
- `scraper/base.py` — BaseScraper + ScraperResult
- `scraper/aca.py` — ACA scraper
- `scraper/ampp.py` — AMPP scraper
- `scraper/tenders_au.py` — AU tender portals scraper
- `scraper/tenders_nz.py` — NZ GETS scraper
- `scraper/trade_shows.py` — Trade show scraper

### Modified Files
- `scraper/linkedin.py` — Refactor to implement BaseScraper
- `scraper/search_engine.py` — Rewrite orchestrator
- `database/models.py` — Add source_url, company_domain fields
- `app.py` — Update routes for multi-source, dedup logic
- `templates/scraper.html` — Tabbed UI, source checkboxes
- `templates/partials/scraper_status.html` — Per-source status + source column
- `templates/partials/scraper_row_added.html` — Add source badge

### Migration
- Alembic migration for new DB columns (or SQLAlchemy `create_all` since SQLite)
