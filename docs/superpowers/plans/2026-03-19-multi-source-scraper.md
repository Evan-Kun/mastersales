# Multi-Source Scraper Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand MasterSales scraper from LinkedIn-only to 6 pluggable industry sources (LinkedIn, ACA, AMPP, AU Tenders, NZ Tenders, Trade Shows) with a tabbed UI, per-source status tracking, and cross-source deduplication.

**Architecture:** Pluggable `BaseScraper` ABC with `ScraperResult` TypedDict contract. Each source is an independent module. Orchestrator runs selected sources in parallel threads with browser concurrency limit. UI uses tabbed Alpine.js layout with HTMX polling.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Playwright, HTMX, Alpine.js, Tailwind CSS

**Spec:** `docs/superpowers/specs/2026-03-19-multi-source-scraper-design.md`

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `scraper/base.py` | `BaseScraper` ABC, `ScraperResult` TypedDict, `ScraperConfig` TypedDict |
| `scraper/aca.py` | ACA scraper (corrosion.com.au) |
| `scraper/ampp.py` | AMPP scraper (ampp.org) |
| `scraper/tenders_au.py` | AU government tender portals (AusTender + 4 state portals) |
| `scraper/tenders_nz.py` | NZ GETS tender portal |
| `scraper/trade_shows.py` | Hardcoded events + generic exhibitor URL scraper |
| `tests/test_base_scraper.py` | Tests for base types, dedup logic, orchestrator |
| `tests/test_scrapers.py` | Tests for individual scraper demo modes |

### Modified Files
| File | Changes |
|------|---------|
| `scraper/linkedin.py` | Refactor to subclass `BaseScraper`, add `source_url`/`source_name` to output |
| `scraper/search_engine.py` | Rewrite: source registry, parallel threaded execution, cross-source dedup |
| `database/models.py` | Add `source_url` to Contact, `company_domain` to Company, widen `lead_source`, drop `linkedin_url` unique |
| `database/db.py` | Add migration for new columns |
| `config.py` | No changes needed (existing `industry_keywords` used by all sources) |
| `app.py` | Multi-source routes, updated dedup, cancel endpoint, per-source status |
| `templates/scraper.html` | Tabbed UI with Alpine.js, source checkboxes, per-source credential forms |
| `templates/partials/scraper_status.html` | Per-source status bars, source column in results table, source filter |
| `templates/partials/scraper_row_added.html` | Add source badge column |

---

## Task 1: BaseScraper Interface + ScraperResult

**Files:**
- Create: `scraper/base.py`
- Test: `tests/test_base_scraper.py`

- [ ] **Step 1: Write the test for ScraperResult validation**

```python
# tests/test_base_scraper.py
from scraper.base import ScraperResult, ScraperConfig, BaseScraper


def test_scraper_result_has_required_fields():
    result: ScraperResult = {
        "first_name": "John",
        "last_name": "Smith",
        "job_title": "Engineer",
        "company_name": "BHP",
        "company_domain": "bhp.com",
        "linkedin_url": None,
        "location_city": "Perth",
        "location_state": "WA",
        "location_country": "AU",
        "source_url": "https://example.com/page",
        "source_name": "ACA",
    }
    assert result["first_name"] == "John"
    assert result["source_name"] == "ACA"
    assert result["company_name"] == "BHP"


def test_scraper_config_accepts_partial():
    config: ScraperConfig = {
        "keywords": ["steel", "corrosion"],
        "location": "Australia",
        "max_results": 20,
    }
    assert config["keywords"] == ["steel", "corrosion"]


def test_base_scraper_cannot_be_instantiated():
    """BaseScraper is abstract — can't instantiate directly."""
    import pytest
    with pytest.raises(TypeError):
        BaseScraper()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/kun/mastersales && python -m pytest tests/test_base_scraper.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scraper.base'`

- [ ] **Step 3: Implement `scraper/base.py`**

```python
# scraper/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypedDict


class ScraperConfig(TypedDict, total=False):
    """Unified config passed to each scraper's scrape() method."""
    keywords: list[str]
    location: str
    max_results: int
    credentials: dict[str, str]
    date_from: str
    date_to: str
    states: list[str]
    event_urls: list[str]
    events: list[str]


class ScraperResult(TypedDict):
    """Universal output contract for all scrapers."""
    first_name: str
    last_name: str
    job_title: str | None
    company_name: str
    company_domain: str | None
    linkedin_url: str | None
    location_city: str | None
    location_state: str | None
    location_country: str | None
    source_url: str | None
    source_name: str


class BaseScraper(ABC):
    """Abstract base for all source scrapers."""

    name: str = ""
    slug: str = ""
    requires_auth: bool = False
    credential_fields: list[dict] = []
    uses_browser: bool = False

    @abstractmethod
    def scrape(self, config: ScraperConfig) -> list[ScraperResult]:
        ...

    @abstractmethod
    def generate_demo_results(self, config: ScraperConfig) -> list[ScraperResult]:
        ...

    def validate_credentials(self, credentials: dict) -> bool:
        return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/kun/mastersales && python -m pytest tests/test_base_scraper.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add scraper/base.py tests/test_base_scraper.py
git commit -m "feat: add BaseScraper interface and ScraperResult contract"
```

---

## Task 2: Database Model Changes + Migration

**Files:**
- Modify: `database/models.py:51-86` (Contact model)
- Modify: `database/models.py:30-48` (Company model)
- Modify: `database/db.py:28-36` (`_run_migrations`)
- Test: `tests/test_base_scraper.py` (add migration tests)

- [ ] **Step 1: Write the test for new model fields**

Add to `tests/test_base_scraper.py`:

```python
def test_contact_has_source_url_field():
    from database.models import Contact
    assert hasattr(Contact, "source_url")


def test_company_has_domain_field():
    from database.models import Company
    assert hasattr(Company, "company_domain")


def test_contact_lead_source_accepts_long_names():
    from database.models import Contact
    col = Contact.__table__.columns["lead_source"]
    assert col.type.length >= 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/kun/mastersales && python -m pytest tests/test_base_scraper.py::test_contact_has_source_url_field tests/test_base_scraper.py::test_company_has_domain_field tests/test_base_scraper.py::test_contact_lead_source_accepts_long_names -v`
Expected: FAIL — `source_url` and `company_domain` don't exist

- [ ] **Step 3: Update `database/models.py`**

Add to `Contact` class (after line 71, after `lead_source`):
```python
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
```

Change `lead_source` from `String(50)` to `String(100)` on line 71.

Change `linkedin_url` on line 63 — remove `unique=True`:
```python
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
```

**NOTE (SQLite limitation):** SQLite does not support `ALTER TABLE DROP CONSTRAINT`. Removing `unique=True` from the model only takes effect on fresh databases. For existing databases, add this migration to `_run_migrations()`:

```python
    # Drop unique constraint on linkedin_url (SQLite requires table recreation)
    if "contacts" in inspector.get_table_names():
        # Check if unique index exists
        indexes = inspector.get_indexes("contacts")
        has_linkedin_unique = any(
            idx.get("unique") and "linkedin_url" in idx.get("column_names", [])
            for idx in indexes
        )
        if has_linkedin_unique:
            with engine.begin() as conn:
                conn.execute(text("DROP INDEX IF EXISTS ix_contacts_linkedin_url"))
```

Add to `Company` class (after line 43, after `company_keywords`):
```python
    company_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
```

- [ ] **Step 4: Update `database/db.py` migration**

Append to the existing `_run_migrations()` function (after the existing `deleted_at` migration block):
```python
        # -- New fields for multi-source scraper --
        if "source_url" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE contacts ADD COLUMN source_url VARCHAR(500)"))

    if "companies" in inspector.get_table_names():
        columns = {c["name"] for c in inspector.get_columns("companies")}
        if "company_domain" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE companies ADD COLUMN company_domain VARCHAR(255)"))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/kun/mastersales && python -m pytest tests/test_base_scraper.py -v`
Expected: 6 PASSED

- [ ] **Step 6: Commit**

```bash
git add database/models.py database/db.py tests/test_base_scraper.py
git commit -m "feat: add source_url, company_domain fields and widen lead_source"
```

---

## Task 3: Orchestrator Rewrite (`search_engine.py`)

**Files:**
- Modify: `scraper/search_engine.py` (full rewrite)
- Test: `tests/test_base_scraper.py` (add orchestrator tests)

- [ ] **Step 1: Write tests for the orchestrator**

Add to `tests/test_base_scraper.py`:

```python
from scraper.base import BaseScraper, ScraperConfig, ScraperResult


class FakeScraperA(BaseScraper):
    name = "Fake A"
    slug = "fake_a"
    requires_auth = False
    uses_browser = False

    def scrape(self, config):
        return [
            {"first_name": "John", "last_name": "Smith", "job_title": "Eng",
             "company_name": "BHP", "company_domain": None, "linkedin_url": None,
             "location_city": "Perth", "location_state": "WA", "location_country": "AU",
             "source_url": "https://a.com", "source_name": "Fake A"},
        ]

    def generate_demo_results(self, config):
        return self.scrape(config)


class FakeScraperB(BaseScraper):
    name = "Fake B"
    slug = "fake_b"
    requires_auth = False
    uses_browser = False

    def scrape(self, config):
        return [
            # Same person as FakeScraperA, but with domain filled in
            {"first_name": "John", "last_name": "Smith", "job_title": "Engineer",
             "company_name": "BHP", "company_domain": "bhp.com", "linkedin_url": None,
             "location_city": "Perth", "location_state": "WA", "location_country": "AU",
             "source_url": "https://b.com", "source_name": "Fake B"},
            # Different person
            {"first_name": "Jane", "last_name": "Doe", "job_title": "PM",
             "company_name": "Rio Tinto", "company_domain": None, "linkedin_url": None,
             "location_city": "Sydney", "location_state": "NSW", "location_country": "AU",
             "source_url": "https://b.com/2", "source_name": "Fake B"},
        ]

    def generate_demo_results(self, config):
        return self.scrape(config)


def test_dedup_merges_cross_source():
    from scraper.search_engine import dedup_results
    results = FakeScraperA().scrape({}) + FakeScraperB().scrape({})
    deduped = dedup_results(results)
    assert len(deduped) == 2  # John Smith merged, Jane Doe kept
    john = [r for r in deduped if r["first_name"] == "John"][0]
    assert john["company_domain"] == "bhp.com"  # Richer record wins
    assert "Fake A" in john["source_name"] and "Fake B" in john["source_name"]


def test_dedup_different_companies_not_merged():
    from scraper.search_engine import dedup_results
    results = [
        {"first_name": "John", "last_name": "Smith", "job_title": "Eng",
         "company_name": "BHP", "company_domain": None, "linkedin_url": None,
         "location_city": None, "location_state": None, "location_country": None,
         "source_url": None, "source_name": "A"},
        {"first_name": "John", "last_name": "Smith", "job_title": "Mgr",
         "company_name": "Rio Tinto", "company_domain": None, "linkedin_url": None,
         "location_city": None, "location_state": None, "location_country": None,
         "source_url": None, "source_name": "B"},
    ]
    deduped = dedup_results(results)
    assert len(deduped) == 2  # Different companies = different leads


def test_run_scrape_multi_source(monkeypatch):
    from scraper import search_engine
    # Patch the registry
    monkeypatch.setattr(search_engine, "SCRAPERS", {
        "fake_a": FakeScraperA,
        "fake_b": FakeScraperB,
    })
    results, status = search_engine.run_scrape(
        sources=["fake_a", "fake_b"],
        keywords=["steel"],
        location="Australia",
        max_results=20,
        credentials={},
        source_configs={},
    )
    assert len(results) == 2  # Deduped
    assert status["total_found"] >= 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/kun/mastersales && python -m pytest tests/test_base_scraper.py::test_dedup_merges_cross_source -v`
Expected: FAIL — `dedup_results` doesn't exist

- [ ] **Step 3: Rewrite `scraper/search_engine.py`**

```python
# scraper/search_engine.py
import logging
import threading
from scraper.base import BaseScraper, ScraperConfig, ScraperResult

logger = logging.getLogger("mastersales.scraper")

# Source registry — populated by imports at bottom
SCRAPERS: dict[str, type[BaseScraper]] = {}

# Thread-safe state
_lock = threading.Lock()
_cancel_event = threading.Event()
_browser_semaphore = threading.Semaphore(2)


def _dedup_key(r: ScraperResult) -> str:
    return f"{r['first_name'].lower().strip()}|{r['last_name'].lower().strip()}|{r['company_name'].lower().strip()}"


def _richness(r: ScraperResult) -> int:
    """Count non-None optional fields."""
    return sum(1 for k in ("job_title", "company_domain", "linkedin_url",
                           "location_city", "location_state", "location_country",
                           "source_url") if r.get(k))


def dedup_results(results: list[ScraperResult]) -> list[ScraperResult]:
    """Cross-source dedup. Same (name, company) = merge, keeping richer record."""
    seen: dict[str, ScraperResult] = {}
    for r in results:
        key = _dedup_key(r)
        if key in seen:
            existing = seen[key]
            # Merge: keep richer record, combine source_names
            if _richness(r) > _richness(existing):
                combined_source = f"{existing['source_name']}, {r['source_name']}"
                seen[key] = {**r, "source_name": combined_source}
            else:
                existing["source_name"] = f"{existing['source_name']}, {r['source_name']}"
        else:
            seen[key] = dict(r)  # copy to avoid mutation
    return list(seen.values())


def run_scrape(
    sources: list[str],
    keywords: list[str],
    location: str = "Australia",
    max_results: int = 20,
    credentials: dict[str, dict] | None = None,
    source_configs: dict | None = None,
) -> tuple[list[ScraperResult], dict]:
    """Run selected scrapers in parallel, dedup, return (results, status)."""
    credentials = credentials or {}
    source_configs = source_configs or {}
    _cancel_event.clear()

    status = {
        "running": True,
        "sources": {},
        "total_found": 0,
    }

    all_results: list[ScraperResult] = []

    def _run_source(slug: str):
        scraper_cls = SCRAPERS.get(slug)
        if not scraper_cls:
            with _lock:
                status["sources"][slug] = {"status": "error", "found": 0, "message": f"Unknown source: {slug}"}
            return

        scraper = scraper_cls()
        with _lock:
            status["sources"][slug] = {"status": "running", "found": 0}

        config: ScraperConfig = {
            "keywords": keywords,
            "location": location,
            "max_results": max_results,
            **source_configs.get(slug, {}),
        }
        if slug in credentials:
            config["credentials"] = credentials[slug]

        try:
            # Acquire browser semaphore if needed
            if scraper.uses_browser:
                _browser_semaphore.acquire()

            try:
                # Use demo mode if auth required but no credentials
                if scraper.requires_auth and not config.get("credentials"):
                    logger.info(f"[{slug}] No credentials — demo mode")
                    results = scraper.generate_demo_results(config)
                else:
                    results = scraper.scrape(config)
            finally:
                if scraper.uses_browser:
                    _browser_semaphore.release()

            with _lock:
                all_results.extend(results)
                status["sources"][slug] = {"status": "complete", "found": len(results)}
                status["total_found"] = len(all_results)
            logger.info(f"[{slug}] Complete: {len(results)} results")

        except Exception as e:
            logger.error(f"[{slug}] Error: {e}")
            with _lock:
                status["sources"][slug] = {"status": "error", "found": 0, "message": str(e)}

    # Launch threads
    threads = []
    for slug in sources:
        t = threading.Thread(target=_run_source, args=(slug,), daemon=True)
        threads.append(t)
        t.start()

    # Wait for all threads
    for t in threads:
        t.join()

    # Cross-source dedup
    deduped = dedup_results(all_results)

    with _lock:
        status["running"] = False
        status["total_found"] = len(deduped)

    logger.info(f"Scrape complete: {len(deduped)} leads after dedup (from {len(all_results)} raw)")
    return deduped, status


def cancel_scrape():
    """Signal all running scrapers to stop."""
    _cancel_event.set()


def is_cancelled() -> bool:
    """Check if cancellation was requested. Scrapers should call this between pages."""
    return _cancel_event.is_set()


# --- Legacy compatibility: demo data generator (moved from old search_engine.py) ---
# Kept here for use by LinkedInScraper.generate_demo_results()

import time
import random

DEMO_FIRST_NAMES = [
    "Michael", "Jennifer", "Robert", "Tane", "Karen", "Steven", "Linda", "Rawiri",
    "Craig", "Priya", "Daniel", "Grace", "Wayne", "Sophie", "Ian", "David",
    "Sarah", "James", "Emily", "Mark", "Aroha", "Peter", "Megan", "Hemi",
    "Andrew", "Rachel", "Scott", "Nikita", "Tom", "Anita", "Brett", "Claire",
    "Nathan", "Lisa", "Aaron", "Deepa", "Paul", "Joanne", "Ravi", "Bridget",
    "Shane", "Kylie", "Liam", "Fatima", "Chris", "Ngaire", "Adam", "Wendy",
    "George", "Tamara", "Marcus", "Ingrid", "Wiremu", "Katrina", "Darren", "Mei",
    "Colin", "Vanessa", "Ethan", "Sonia",
]

DEMO_LAST_NAMES = [
    "Anderson", "Walsh", "Hughes", "Wiremu", "Mitchell", "Park", "Foster", "Henare",
    "McDonald", "Sharma", "O'Sullivan", "Lee", "Barrett", "Turner", "Campbell", "Clarke",
    "Richards", "Patel", "Thompson", "Cooper", "Singh", "Jenkins", "Harris", "Taylor",
    "Brown", "Wilson", "O'Brien", "Martin", "Young", "King", "White", "Robinson",
    "Wright", "Nguyen", "Stewart", "Kelly", "Davis", "Zhang", "Morgan", "Baker",
    "Scott", "Murray", "Wood", "Morris", "Gray", "Mason", "Bell", "Duncan",
    "Ross", "Fraser", "Hamilton", "Crawford", "Johnston", "Kaur", "Adams", "Gordon",
    "Stone", "Fox", "Blair", "Cole",
]

DEMO_COMPANIES = [
    ("Precision Steel WA", "Perth", "WA", "AU"),
    ("AusCoat Solutions", "Melbourne", "VIC", "AU"),
    ("Iron Range Mining", "Kalgoorlie", "WA", "AU"),
    ("Pacific Dockyard NZ", "Wellington", "Wellington", "NZ"),
    ("BHP Nickel West", "Perth", "WA", "AU"),
    ("Steel Blue Fabrications", "Geelong", "VIC", "AU"),
    ("Fortescue Metals Group", "Port Hedland", "WA", "AU"),
    ("Kiwi Steel Structures", "Auckland", "Auckland", "NZ"),
    ("Coastal Engineering VIC", "Frankston", "VIC", "AU"),
    ("Rio Tinto Iron Ore", "Newman", "WA", "AU"),
    ("Murray Steel Works", "Ballarat", "VIC", "AU"),
    ("Downer Group", "Perth", "WA", "AU"),
    ("Tasman Steel NZ", "Christchurch", "Canterbury", "NZ"),
    ("BlueScope Steel", "Melbourne", "VIC", "AU"),
    ("Newmont Boddington", "Boddington", "WA", "AU"),
    ("Civmec Construction", "Henderson", "WA", "AU"),
    ("Monadelphous Group", "Perth", "WA", "AU"),
    ("NZ Steel", "Glenbrook", "Waikato", "NZ"),
    ("Southern Cross Fabrication", "Bunbury", "WA", "AU"),
    ("OneSteel Metalcentre", "Dandenong", "VIC", "AU"),
]


def generate_demo_data(
    keywords: list[str],
    max_results: int,
    source_name: str,
    job_titles: list[str],
    source_url_base: str = "https://demo.example.com",
) -> list[ScraperResult]:
    """Shared demo data generator. Seeded by keywords for deterministic output."""
    seed = hash((tuple(sorted(keywords)), source_name)) & 0xFFFFFFFF
    rng = random.Random(seed)

    results = []
    used_names = set()

    for i in range(max_results):
        for _ in range(50):
            first = rng.choice(DEMO_FIRST_NAMES)
            last = rng.choice(DEMO_LAST_NAMES)
            if (first, last) not in used_names:
                used_names.add((first, last))
                break

        title = rng.choice(job_titles)
        company, city, state, country = rng.choice(DEMO_COMPANIES)

        results.append({
            "first_name": first,
            "last_name": last,
            "job_title": title,
            "company_name": company,
            "company_domain": None,
            "linkedin_url": None,
            "location_city": city,
            "location_state": state,
            "location_country": country,
            "source_url": f"{source_url_base}/demo/{i}",
            "source_name": source_name,
        })

    return results


# Register all scrapers (lazy imports to avoid circular deps)
def _register_scrapers():
    global SCRAPERS
    from scraper.linkedin import LinkedInScraper
    from scraper.aca import ACAScraper
    from scraper.ampp import AMPPScraper
    from scraper.tenders_au import AusTenderScraper
    from scraper.tenders_nz import GETSScraper
    from scraper.trade_shows import TradeShowScraper

    SCRAPERS = {
        "linkedin": LinkedInScraper,
        "aca": ACAScraper,
        "ampp": AMPPScraper,
        "tenders_au": AusTenderScraper,
        "tenders_nz": GETSScraper,
        "trade_shows": TradeShowScraper,
    }
```

**NOTE:** `_register_scrapers()` is defined but NOT called at module level in this task. It imports all 6 scrapers, which don't exist yet (Tasks 4-9). It will be called in Task 10 after all scrapers are created.

- [ ] **Step 4: Add cancel test**

Add to `tests/test_base_scraper.py`:

```python
def test_cancel_and_is_cancelled():
    from scraper.search_engine import cancel_scrape, is_cancelled, _cancel_event
    _cancel_event.clear()
    assert is_cancelled() is False
    cancel_scrape()
    assert is_cancelled() is True
    _cancel_event.clear()  # cleanup
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/kun/mastersales && python -m pytest tests/test_base_scraper.py -v`
Expected: All PASSED (the `run_scrape_multi_source` test uses monkeypatched fakes, not real scrapers)

- [ ] **Step 6: Commit**

```bash
git add scraper/search_engine.py tests/test_base_scraper.py
git commit -m "feat: rewrite orchestrator with parallel execution and cross-source dedup"
```

---

## Task 4: LinkedIn Scraper Refactor

**Files:**
- Modify: `scraper/linkedin.py:1-30` (imports + class declaration)
- Modify: `scraper/linkedin.py` (wrap `search_people` as `scrape`)
- Test: `tests/test_scrapers.py`

- [ ] **Step 1: Write test for LinkedIn scraper interface**

```python
# tests/test_scrapers.py
from scraper.base import BaseScraper


def test_linkedin_scraper_is_base_scraper():
    from scraper.linkedin import LinkedInScraper
    scraper = LinkedInScraper.__new__(LinkedInScraper)
    assert isinstance(scraper, BaseScraper)
    assert scraper.slug == "linkedin"
    assert scraper.uses_browser is True
    assert scraper.requires_auth is True


def test_linkedin_demo_results():
    from scraper.linkedin import LinkedInScraper
    scraper = LinkedInScraper.__new__(LinkedInScraper)
    results = scraper.generate_demo_results({
        "keywords": ["steel", "corrosion"],
        "max_results": 5,
    })
    assert len(results) == 5
    assert all(r["source_name"] == "LinkedIn" for r in results)
    assert all(r["first_name"] and r["last_name"] for r in results)
    assert all(r["company_name"] for r in results)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/kun/mastersales && python -m pytest tests/test_scrapers.py::test_linkedin_scraper_is_base_scraper -v`
Expected: FAIL

- [ ] **Step 3: Refactor `scraper/linkedin.py`**

Key changes (minimal — preserve all existing scraping logic):

1. Import and subclass `BaseScraper`:
```python
from scraper.base import BaseScraper, ScraperConfig, ScraperResult
```

2. Change class declaration:
```python
class LinkedInScraper(BaseScraper):
    name = "LinkedIn"
    slug = "linkedin"
    requires_auth = True
    uses_browser = True
    credential_fields = [
        {"key": "email", "label": "LinkedIn Email", "type": "email"},
        {"key": "password", "label": "LinkedIn Password", "type": "password"},
    ]
```

3. Add `scrape()` method that wraps existing `search_people()`:
```python
    def scrape(self, config: ScraperConfig) -> list[ScraperResult]:
        creds = config.get("credentials", {})
        email = creds.get("email", "")
        password = creds.get("password", "")
        if not email or not password:
            return self.generate_demo_results(config)

        self.email = email
        self.password = password
        raw_results = self.search_people(
            config.get("keywords", []),
            config.get("location", "Australia"),
            config.get("max_results", 20),
        )
        # Convert to ScraperResult format
        return [
            {
                "first_name": r.get("first_name", ""),
                "last_name": r.get("last_name", ""),
                "job_title": r.get("job_title"),
                "company_name": r.get("company_name", "Unknown"),
                "company_domain": None,
                "linkedin_url": r.get("linkedin_url"),
                "location_city": r.get("location_city"),
                "location_state": r.get("location_state"),
                "location_country": r.get("location_country"),
                "source_url": r.get("linkedin_url"),
                "source_name": "LinkedIn",
            }
            for r in raw_results
        ]
```

4. Add `generate_demo_results()`:
```python
    def generate_demo_results(self, config: ScraperConfig) -> list[ScraperResult]:
        from scraper.search_engine import generate_demo_data
        titles = [
            "Steel Fabrication Manager", "Corrosion Engineer", "Maintenance Director",
            "Procurement Specialist", "Quality Control Manager", "Site Engineer",
            "Materials Engineer", "Plant Manager", "Operations Manager",
        ]
        results = generate_demo_data(
            keywords=config.get("keywords", []),
            max_results=config.get("max_results", 20),
            source_name="LinkedIn",
            job_titles=titles,
            source_url_base="https://linkedin.com/in",
        )
        # Add linkedin_url for demo
        for r in results:
            slug = f"{r['first_name'].lower()}-{r['last_name'].lower()}-demo"
            r["linkedin_url"] = f"https://linkedin.com/in/{slug}"
        return results
```

5. Keep existing `__init__(self, email, password)` and `search_people()` — they still work for the `scrape()` wrapper. Remove the email/password from `__init__` requirement by making them optional with defaults:
```python
    def __init__(self, email: str = "", password: str = ""):
```

- [ ] **Step 4: Run tests**

Run: `cd /home/kun/mastersales && python -m pytest tests/test_scrapers.py -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add scraper/linkedin.py tests/test_scrapers.py
git commit -m "refactor: wrap LinkedInScraper in BaseScraper interface"
```

---

## Task 5: ACA Scraper

**Files:**
- Create: `scraper/aca.py`
- Test: `tests/test_scrapers.py` (add tests)

- [ ] **Step 1: Write test for ACA demo mode**

Add to `tests/test_scrapers.py`:

```python
def test_aca_scraper_interface():
    from scraper.aca import ACAScraper
    scraper = ACAScraper()
    assert isinstance(scraper, BaseScraper)
    assert scraper.slug == "aca"
    assert scraper.requires_auth is False  # public-first


def test_aca_demo_results():
    from scraper.aca import ACAScraper
    scraper = ACAScraper()
    results = scraper.generate_demo_results({
        "keywords": ["corrosion"],
        "max_results": 5,
    })
    assert len(results) == 5
    assert all(r["source_name"] == "ACA" for r in results)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/kun/mastersales && python -m pytest tests/test_scrapers.py::test_aca_scraper_interface -v`
Expected: FAIL

- [ ] **Step 3: Implement `scraper/aca.py`**

```python
# scraper/aca.py
import logging
from scraper.base import BaseScraper, ScraperConfig, ScraperResult

logger = logging.getLogger("mastersales.scraper.aca")


class ACAScraper(BaseScraper):
    name = "ACA"
    slug = "aca"
    requires_auth = False  # Try public pages first
    uses_browser = True
    credential_fields = [
        {"key": "username", "label": "ACA Username", "type": "text"},
        {"key": "password", "label": "ACA Password", "type": "password"},
    ]

    def scrape(self, config: ScraperConfig) -> list[ScraperResult]:
        """Scrape corrosion.com.au for member/event data."""
        from scraper.search_engine import is_cancelled

        max_results = config.get("max_results", 20)
        keywords = config.get("keywords", [])
        results: list[ScraperResult] = []

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning("[ACA] Playwright not installed — demo mode")
            return self.generate_demo_results(config)

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # Scrape public pages: events, committees, technical papers
                target_urls = [
                    "https://www.corrosion.com.au/events",
                    "https://www.corrosion.com.au/about/committees",
                    "https://www.corrosion.com.au/resources/technical-papers",
                ]

                for url in target_urls:
                    if is_cancelled() or len(results) >= max_results:
                        break

                    try:
                        page.goto(url, timeout=15000)
                        page.wait_for_load_state("domcontentloaded", timeout=10000)

                        # Extract person cards/entries from page
                        entries = self._extract_people_from_page(page, url)
                        results.extend(entries)
                        logger.info(f"[ACA] {url}: found {len(entries)} entries")
                    except Exception as e:
                        logger.warning(f"[ACA] Failed to scrape {url}: {e}")

                # If auth provided, try member directory
                creds = config.get("credentials", {})
                if creds.get("username") and creds.get("password") and len(results) < max_results:
                    try:
                        self._login(page, creds["username"], creds["password"])
                        member_results = self._scrape_member_directory(page, max_results - len(results))
                        results.extend(member_results)
                    except Exception as e:
                        logger.warning(f"[ACA] Member directory login failed: {e}")

                browser.close()

        except Exception as e:
            logger.error(f"[ACA] Scraper error: {e}")

        return results[:max_results]

    def _extract_people_from_page(self, page, url: str) -> list[ScraperResult]:
        """Extract person data from common HTML patterns on ACA pages."""
        results = []
        # Try common selectors for person cards
        selectors = [
            ".person-card", ".speaker-card", ".member-item",
            ".committee-member", "article.person",
            "table tbody tr", ".card",
        ]

        for selector in selectors:
            elements = page.query_selector_all(selector)
            if not elements:
                continue

            for el in elements:
                text = el.inner_text()
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                if len(lines) < 1:
                    continue

                # Try to parse name from first line
                name_parts = lines[0].split()
                if len(name_parts) < 2:
                    continue

                first_name = name_parts[0]
                last_name = " ".join(name_parts[1:])
                job_title = lines[1] if len(lines) > 1 else None
                company = lines[2] if len(lines) > 2 else "Unknown"

                results.append({
                    "first_name": first_name,
                    "last_name": last_name,
                    "job_title": job_title,
                    "company_name": company,
                    "company_domain": None,
                    "linkedin_url": None,
                    "location_city": None,
                    "location_state": None,
                    "location_country": "AU",
                    "source_url": url,
                    "source_name": "ACA",
                })
            if results:
                break  # Found data with this selector

        return results

    def _login(self, page, username: str, password: str):
        """Attempt ACA member login."""
        page.goto("https://www.corrosion.com.au/login", timeout=15000)
        page.fill('input[name="username"], input[type="email"]', username)
        page.fill('input[type="password"]', password)
        page.click('button[type="submit"], input[type="submit"]')
        page.wait_for_load_state("domcontentloaded", timeout=10000)

    def _scrape_member_directory(self, page, max_results: int) -> list[ScraperResult]:
        """Scrape the gated member directory after login."""
        results = []
        try:
            page.goto("https://www.corrosion.com.au/members/directory", timeout=15000)
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            results = self._extract_people_from_page(page, "https://www.corrosion.com.au/members/directory")
        except Exception as e:
            logger.warning(f"[ACA] Member directory scrape failed: {e}")
        return results[:max_results]

    def generate_demo_results(self, config: ScraperConfig) -> list[ScraperResult]:
        from scraper.search_engine import generate_demo_data
        titles = [
            "Corrosion Scientist", "ACA Committee Member", "Cathodic Protection Engineer",
            "Corrosion Inspector", "Materials Scientist", "Coatings Specialist",
            "Research Fellow - Corrosion", "Technical Director", "ACA Branch Chair",
        ]
        return generate_demo_data(
            keywords=config.get("keywords", []),
            max_results=config.get("max_results", 20),
            source_name="ACA",
            job_titles=titles,
            source_url_base="https://corrosion.com.au",
        )
```

- [ ] **Step 4: Run tests**

Run: `cd /home/kun/mastersales && python -m pytest tests/test_scrapers.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add scraper/aca.py tests/test_scrapers.py
git commit -m "feat: add ACA scraper with public + auth modes"
```

---

## Task 6: AMPP Scraper

**Files:**
- Create: `scraper/ampp.py`
- Test: `tests/test_scrapers.py` (add tests)

- [ ] **Step 1: Write test**

Add to `tests/test_scrapers.py`:

```python
def test_ampp_scraper_interface():
    from scraper.ampp import AMPPScraper
    scraper = AMPPScraper()
    assert isinstance(scraper, BaseScraper)
    assert scraper.slug == "ampp"
    assert scraper.requires_auth is False


def test_ampp_demo_results():
    from scraper.ampp import AMPPScraper
    results = AMPPScraper().generate_demo_results({"keywords": ["coating"], "max_results": 5})
    assert len(results) == 5
    assert all(r["source_name"] == "AMPP" for r in results)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/kun/mastersales && python -m pytest tests/test_scrapers.py::test_ampp_scraper_interface -v`
Expected: FAIL

- [ ] **Step 3: Implement `scraper/ampp.py`**

```python
# scraper/ampp.py
import logging
from scraper.base import BaseScraper, ScraperConfig, ScraperResult

logger = logging.getLogger("mastersales.scraper.ampp")


class AMPPScraper(BaseScraper):
    """AMPP (formerly NACE) community directory scraper."""
    name = "AMPP"
    slug = "ampp"
    requires_auth = False  # Try public pages first
    uses_browser = True
    credential_fields = [
        {"key": "username", "label": "AMPP Username", "type": "text"},
        {"key": "password", "label": "AMPP Password", "type": "password"},
    ]

    def scrape(self, config: ScraperConfig) -> list[ScraperResult]:
        from scraper.search_engine import is_cancelled

        max_results = config.get("max_results", 20)
        results: list[ScraperResult] = []

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning("[AMPP] Playwright not installed — demo mode")
            return self.generate_demo_results(config)

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # Public pages: conference speakers, AU chapter, events
                target_urls = [
                    "https://www.ampp.org/events",
                    "https://www.ampp.org/community/sections-and-chapters",
                    "https://www.ampp.org/education/certification",
                ]

                for url in target_urls:
                    if is_cancelled() or len(results) >= max_results:
                        break
                    try:
                        page.goto(url, timeout=15000)
                        page.wait_for_load_state("domcontentloaded", timeout=10000)
                        entries = self._extract_people_from_page(page, url)
                        results.extend(entries)
                        logger.info(f"[AMPP] {url}: found {len(entries)} entries")
                    except Exception as e:
                        logger.warning(f"[AMPP] Failed to scrape {url}: {e}")

                # Auth-gated member directory
                creds = config.get("credentials", {})
                if creds.get("username") and creds.get("password") and len(results) < max_results:
                    try:
                        page.goto("https://www.ampp.org/login", timeout=15000)
                        page.fill('input[name="username"], input[type="email"]', creds["username"])
                        page.fill('input[type="password"]', creds["password"])
                        page.click('button[type="submit"], input[type="submit"]')
                        page.wait_for_load_state("domcontentloaded", timeout=10000)

                        page.goto("https://www.ampp.org/community/member-directory", timeout=15000)
                        entries = self._extract_people_from_page(
                            page, "https://www.ampp.org/community/member-directory"
                        )
                        results.extend(entries)
                    except Exception as e:
                        logger.warning(f"[AMPP] Member directory login failed: {e}")

                browser.close()
        except Exception as e:
            logger.error(f"[AMPP] Scraper error: {e}")

        return results[:max_results]

    def _extract_people_from_page(self, page, url: str) -> list[ScraperResult]:
        """Extract person data from common HTML patterns on AMPP pages."""
        results = []
        selectors = [
            ".person-card", ".speaker-card", ".member-item",
            "table tbody tr", ".card", ".profile-item",
        ]

        for selector in selectors:
            elements = page.query_selector_all(selector)
            if not elements:
                continue
            for el in elements:
                text = el.inner_text()
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                if len(lines) < 1:
                    continue
                name_parts = lines[0].split()
                if len(name_parts) < 2:
                    continue
                results.append({
                    "first_name": name_parts[0],
                    "last_name": " ".join(name_parts[1:]),
                    "job_title": lines[1] if len(lines) > 1 else None,
                    "company_name": lines[2] if len(lines) > 2 else "Unknown",
                    "company_domain": None,
                    "linkedin_url": None,
                    "location_city": None,
                    "location_state": None,
                    "location_country": "AU",
                    "source_url": url,
                    "source_name": "AMPP",
                })
            if results:
                break
        return results

    def generate_demo_results(self, config: ScraperConfig) -> list[ScraperResult]:
        from scraper.search_engine import generate_demo_data
        titles = [
            "AMPP Certified Inspector", "Protective Coatings Specialist",
            "NACE Level III Inspector", "Cathodic Protection Technician",
            "Coatings Application Supervisor", "Materials Engineer",
            "Pipeline Integrity Specialist", "Corrosion Technologist",
            "AMPP Chapter Chair - Australia",
        ]
        return generate_demo_data(
            keywords=config.get("keywords", []),
            max_results=config.get("max_results", 20),
            source_name="AMPP",
            job_titles=titles,
            source_url_base="https://ampp.org",
        )
```

- [ ] **Step 4: Run tests, commit**

Run: `cd /home/kun/mastersales && python -m pytest tests/test_scrapers.py -v`
Expected: 6 PASSED

```bash
git add scraper/ampp.py tests/test_scrapers.py
git commit -m "feat: add AMPP scraper with public + auth modes"
```

---

## Task 7: AU Tenders Scraper

**Files:**
- Create: `scraper/tenders_au.py`
- Test: `tests/test_scrapers.py` (add tests)

- [ ] **Step 1: Write test**

Add to `tests/test_scrapers.py`:

```python
def test_au_tenders_scraper_interface():
    from scraper.tenders_au import AusTenderScraper
    scraper = AusTenderScraper()
    assert isinstance(scraper, BaseScraper)
    assert scraper.slug == "tenders_au"
    assert scraper.requires_auth is False
    assert scraper.uses_browser is True


def test_au_tenders_demo_results():
    from scraper.tenders_au import AusTenderScraper
    results = AusTenderScraper().generate_demo_results({
        "keywords": ["steel"], "max_results": 5,
    })
    assert len(results) == 5
    assert all(r["source_name"] == "AusTender" for r in results)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/kun/mastersales && python -m pytest tests/test_scrapers.py::test_au_tenders_scraper_interface -v`
Expected: FAIL

- [ ] **Step 3: Implement `scraper/tenders_au.py`**

```python
# scraper/tenders_au.py
import logging
from datetime import datetime, timedelta
from scraper.base import BaseScraper, ScraperConfig, ScraperResult

logger = logging.getLogger("mastersales.scraper.tenders_au")

# Portal configs: slug -> (name, search URL template)
AU_PORTALS = {
    "austender": {
        "name": "AusTender",
        "base_url": "https://www.tenders.gov.au",
        "search_path": "/Search/KeywordSearch",
    },
    "qtenders": {
        "name": "QTenders",
        "base_url": "https://qtenders.epw.qld.gov.au",
        "search_path": "/qtenders/tender/search",
        "state": "QLD",
    },
    "etendering": {
        "name": "eTendering",
        "base_url": "https://tenders.nsw.gov.au",
        "search_path": "/",
        "state": "NSW",
    },
    "tenders_vic": {
        "name": "Tenders VIC",
        "base_url": "https://www.tenders.vic.gov.au",
        "search_path": "/tender/search",
        "state": "VIC",
    },
    "gems_wa": {
        "name": "GEMS WA",
        "base_url": "https://www.tenders.wa.gov.au",
        "search_path": "/watenders/tender/search",
        "state": "WA",
    },
}


class AusTenderScraper(BaseScraper):
    """Australian government tender portals scraper."""
    name = "AU Tenders"
    slug = "tenders_au"
    requires_auth = False
    uses_browser = True  # Most portals use JS rendering
    credential_fields = []

    def scrape(self, config: ScraperConfig) -> list[ScraperResult]:
        from scraper.search_engine import is_cancelled

        max_results = config.get("max_results", 20)
        keywords = config.get("keywords", [])
        states = config.get("states", [])  # Filter: ["QLD", "WA", ...] or empty = all
        results: list[ScraperResult] = []

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning("[AU Tenders] Playwright not installed — demo mode")
            return self.generate_demo_results(config)

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # Always scrape AusTender (federal)
                portals_to_scrape = ["austender"]
                # Add state portals based on filter
                for slug, portal in AU_PORTALS.items():
                    if slug == "austender":
                        continue
                    if not states or portal.get("state") in states:
                        portals_to_scrape.append(slug)

                for portal_slug in portals_to_scrape:
                    if is_cancelled() or len(results) >= max_results:
                        break

                    portal = AU_PORTALS[portal_slug]
                    try:
                        entries = self._scrape_portal(
                            page, portal, keywords, config, max_results - len(results)
                        )
                        results.extend(entries)
                        logger.info(f"[AU Tenders] {portal['name']}: found {len(entries)} entries")
                    except Exception as e:
                        logger.warning(f"[AU Tenders] {portal['name']} failed: {e}")

                browser.close()
        except Exception as e:
            logger.error(f"[AU Tenders] Scraper error: {e}")

        return results[:max_results]

    def _scrape_portal(
        self, page, portal: dict, keywords: list[str], config: ScraperConfig, limit: int
    ) -> list[ScraperResult]:
        """Scrape a single tender portal for awarded contracts matching keywords."""
        results = []
        keyword_str = " ".join(keywords[:3])  # Most portals limit search terms
        url = f"{portal['base_url']}{portal['search_path']}"

        try:
            page.goto(url, timeout=20000)
            page.wait_for_load_state("domcontentloaded", timeout=15000)

            # Try to find and fill search input
            search_selectors = [
                'input[name="keyword"]', 'input[name="search"]',
                'input[name="q"]', 'input[type="search"]',
                'input[name="SearchKeyword"]', '#keyword',
            ]
            filled = False
            for sel in search_selectors:
                try:
                    el = page.query_selector(sel)
                    if el:
                        el.fill(keyword_str)
                        filled = True
                        break
                except Exception:
                    continue

            if filled:
                # Submit search
                submit_selectors = [
                    'button[type="submit"]', 'input[type="submit"]',
                    'button.search-btn', '#searchButton',
                ]
                for sel in submit_selectors:
                    try:
                        btn = page.query_selector(sel)
                        if btn:
                            btn.click()
                            page.wait_for_load_state("domcontentloaded", timeout=15000)
                            break
                    except Exception:
                        continue

            # Extract results from table rows or cards
            results = self._extract_tender_results(page, portal)

        except Exception as e:
            logger.warning(f"[AU Tenders] Portal {portal['name']} scrape error: {e}")

        return results[:limit]

    def _extract_tender_results(self, page, portal: dict) -> list[ScraperResult]:
        """Extract company/contact data from tender search results."""
        results = []
        row_selectors = [
            "table tbody tr", ".search-result", ".tender-item",
            ".result-item", "article", ".list-group-item",
        ]

        for selector in row_selectors:
            rows = page.query_selector_all(selector)
            if not rows:
                continue

            for row in rows:
                text = row.inner_text()
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                if len(lines) < 2:
                    continue

                # Tender results typically have: title, agency/company, status, dates
                # Extract company name (usually the supplier/awardee)
                company_name = None
                contact_name = None

                for line in lines:
                    # Look for company-like patterns
                    if any(kw in line.lower() for kw in ("pty ltd", "group", "services", "engineering", "steel")):
                        company_name = line.strip()
                    # Look for contact officer pattern
                    if "contact" in line.lower() and ":" in line:
                        contact_name = line.split(":")[-1].strip()

                if not company_name:
                    company_name = lines[1] if len(lines) > 1 else "Unknown"

                # Parse contact name
                first_name = "Unknown"
                last_name = "Contact"
                if contact_name:
                    parts = contact_name.split()
                    if len(parts) >= 2:
                        first_name = parts[0]
                        last_name = " ".join(parts[1:])
                    elif len(parts) == 1:
                        first_name = parts[0]

                # Try to find link for source_url
                link = row.query_selector("a[href]")
                source_url = None
                if link:
                    href = link.get_attribute("href")
                    if href:
                        source_url = href if href.startswith("http") else f"{portal['base_url']}{href}"

                results.append({
                    "first_name": first_name,
                    "last_name": last_name,
                    "job_title": "Contract Officer",
                    "company_name": company_name,
                    "company_domain": None,
                    "linkedin_url": None,
                    "location_city": None,
                    "location_state": portal.get("state"),
                    "location_country": "AU",
                    "source_url": source_url or f"{portal['base_url']}{portal['search_path']}",
                    "source_name": portal["name"],
                })

            if results:
                break

        return results

    def generate_demo_results(self, config: ScraperConfig) -> list[ScraperResult]:
        from scraper.search_engine import generate_demo_data
        titles = [
            "Contract Officer", "Procurement Manager", "Tender Coordinator",
            "Contracts Administrator", "Project Director", "Supply Chain Manager",
            "Infrastructure Procurement Lead", "Senior Buyer", "Vendor Manager",
        ]
        return generate_demo_data(
            keywords=config.get("keywords", []),
            max_results=config.get("max_results", 20),
            source_name="AusTender",
            job_titles=titles,
            source_url_base="https://tenders.gov.au",
        )
```

- [ ] **Step 4: Run tests, commit**

Run: `cd /home/kun/mastersales && python -m pytest tests/test_scrapers.py -v`
Expected: 8 PASSED

```bash
git add scraper/tenders_au.py tests/test_scrapers.py
git commit -m "feat: add AU tenders scraper (AusTender + 4 state portals)"
```

---

## Task 8: NZ Tenders Scraper

**Files:**
- Create: `scraper/tenders_nz.py`
- Test: `tests/test_scrapers.py`

- [ ] **Step 1: Write test**

Add to `tests/test_scrapers.py`:

```python
def test_nz_tenders_scraper_interface():
    from scraper.tenders_nz import GETSScraper
    scraper = GETSScraper()
    assert isinstance(scraper, BaseScraper)
    assert scraper.slug == "tenders_nz"
    assert scraper.requires_auth is False


def test_nz_tenders_demo_results():
    from scraper.tenders_nz import GETSScraper
    results = GETSScraper().generate_demo_results({"keywords": ["steel"], "max_results": 5})
    assert len(results) == 5
    assert all(r["source_name"] == "GETS" for r in results)
    assert all(r["location_country"] == "NZ" for r in results)
```

- [ ] **Step 2: Implement `scraper/tenders_nz.py`**

```python
# scraper/tenders_nz.py
import logging
from scraper.base import BaseScraper, ScraperConfig, ScraperResult

logger = logging.getLogger("mastersales.scraper.tenders_nz")


class GETSScraper(BaseScraper):
    """NZ Government Electronic Tenders Service scraper."""
    name = "NZ Tenders"
    slug = "tenders_nz"
    requires_auth = False
    uses_browser = True
    credential_fields = []

    GETS_BASE = "https://www.gets.govt.nz"
    GETS_SEARCH = "/ExternalIndex.htm"

    def scrape(self, config: ScraperConfig) -> list[ScraperResult]:
        from scraper.search_engine import is_cancelled

        max_results = config.get("max_results", 20)
        keywords = config.get("keywords", [])
        results: list[ScraperResult] = []

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning("[GETS] Playwright not installed — demo mode")
            return self.generate_demo_results(config)

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                keyword_str = " ".join(keywords[:3])
                page.goto(f"{self.GETS_BASE}{self.GETS_SEARCH}", timeout=20000)
                page.wait_for_load_state("domcontentloaded", timeout=15000)

                # Try to fill search
                search_selectors = [
                    'input[name="keyword"]', 'input[name="search"]',
                    'input[name="q"]', 'input[type="search"]', '#keyword',
                ]
                for sel in search_selectors:
                    try:
                        el = page.query_selector(sel)
                        if el:
                            el.fill(keyword_str)
                            break
                    except Exception:
                        continue

                # Submit
                for sel in ['button[type="submit"]', 'input[type="submit"]', '.search-btn']:
                    try:
                        btn = page.query_selector(sel)
                        if btn:
                            btn.click()
                            page.wait_for_load_state("domcontentloaded", timeout=15000)
                            break
                    except Exception:
                        continue

                # Extract from table rows
                for selector in ["table tbody tr", ".search-result", ".tender-item", "article"]:
                    rows = page.query_selector_all(selector)
                    if not rows:
                        continue
                    for row in rows:
                        if is_cancelled() or len(results) >= max_results:
                            break
                        text = row.inner_text()
                        lines = [l.strip() for l in text.split("\n") if l.strip()]
                        if len(lines) < 2:
                            continue

                        company_name = None
                        for line in lines:
                            if any(kw in line.lower() for kw in ("ltd", "limited", "group", "services", "steel")):
                                company_name = line.strip()
                                break
                        if not company_name:
                            company_name = lines[1] if len(lines) > 1 else "Unknown"

                        link = row.query_selector("a[href]")
                        source_url = None
                        if link:
                            href = link.get_attribute("href")
                            if href:
                                source_url = href if href.startswith("http") else f"{self.GETS_BASE}{href}"

                        results.append({
                            "first_name": "Unknown",
                            "last_name": "Contact",
                            "job_title": "Procurement Officer",
                            "company_name": company_name,
                            "company_domain": None,
                            "linkedin_url": None,
                            "location_city": None,
                            "location_state": None,
                            "location_country": "NZ",
                            "source_url": source_url or f"{self.GETS_BASE}{self.GETS_SEARCH}",
                            "source_name": "GETS",
                        })
                    if results:
                        break

                browser.close()
        except Exception as e:
            logger.error(f"[GETS] Scraper error: {e}")

        return results[:max_results]

    def generate_demo_results(self, config: ScraperConfig) -> list[ScraperResult]:
        from scraper.search_engine import generate_demo_data

        NZ_COMPANIES = [
            ("Pacific Dockyard NZ", "Wellington", None, "NZ"),
            ("Kiwi Steel Structures", "Auckland", None, "NZ"),
            ("Tasman Steel NZ", "Christchurch", None, "NZ"),
            ("NZ Steel", "Glenbrook", None, "NZ"),
            ("Fletcher Steel NZ", "Hamilton", None, "NZ"),
            ("Steel & Tube NZ", "Lower Hutt", None, "NZ"),
        ]
        titles = [
            "Procurement Officer", "Contract Manager", "Tender Coordinator",
            "Senior Buyer", "Supply Chain Manager", "Project Director",
        ]

        # Use generate_demo_data but override location to NZ
        results = generate_demo_data(
            keywords=config.get("keywords", []),
            max_results=config.get("max_results", 20),
            source_name="GETS",
            job_titles=titles,
            source_url_base="https://gets.govt.nz",
        )
        # Override all locations to NZ
        for r in results:
            r["location_country"] = "NZ"
        return results
```

- [ ] **Step 3: Run tests, commit**

Run: `cd /home/kun/mastersales && python -m pytest tests/test_scrapers.py -v`
Expected: 10 PASSED

```bash
git add scraper/tenders_nz.py tests/test_scrapers.py
git commit -m "feat: add NZ GETS tenders scraper"
```

---

## Task 9: Trade Shows Scraper

**Files:**
- Create: `scraper/trade_shows.py`
- Test: `tests/test_scrapers.py`

- [ ] **Step 1: Write test**

Add to `tests/test_scrapers.py`:

```python
def test_trade_shows_scraper_interface():
    from scraper.trade_shows import TradeShowScraper
    scraper = TradeShowScraper()
    assert isinstance(scraper, BaseScraper)
    assert scraper.slug == "trade_shows"
    assert scraper.uses_browser is True


def test_trade_shows_demo_with_events():
    from scraper.trade_shows import TradeShowScraper, HARDCODED_EVENTS
    results = TradeShowScraper().generate_demo_results({
        "keywords": ["steel"], "max_results": 5,
    })
    assert len(results) == 5
    assert all("Trade Show" in r["source_name"] for r in results)
    # Verify hardcoded events exist
    assert "aca_conf" in HARDCODED_EVENTS
    assert "austmine" in HARDCODED_EVENTS
```

- [ ] **Step 2: Implement `scraper/trade_shows.py`**

```python
# scraper/trade_shows.py
import logging
from scraper.base import BaseScraper, ScraperConfig, ScraperResult

logger = logging.getLogger("mastersales.scraper.trade_shows")

HARDCODED_EVENTS = {
    "aca_conf": {
        "name": "Australasian Corrosion Conference",
        "urls": [
            "https://www.corrosion.com.au/events/australasian-corrosion-conference",
            "https://www.corrosion.com.au/conference/exhibitors",
        ],
    },
    "austmine": {
        "name": "Austmine Conference",
        "urls": [
            "https://www.austmine.com.au/events",
            "https://www.austmine.com.au/conference/exhibitors",
        ],
    },
    "ampp_annual": {
        "name": "AMPP Annual Conference",
        "urls": [
            "https://www.ampp.org/events/annual-conference",
            "https://www.ampp.org/events/annual-conference/exhibitors",
        ],
    },
    "steel_australia": {
        "name": "Steel Australia Conference",
        "urls": [
            "https://www.steel.org.au/events",
            "https://www.steel.org.au/conference/exhibitors",
        ],
    },
}


class TradeShowScraper(BaseScraper):
    """Trade show exhibitor/speaker scraper with hardcoded events + generic URL mode."""
    name = "Trade Shows"
    slug = "trade_shows"
    requires_auth = False
    uses_browser = True
    credential_fields = []

    def scrape(self, config: ScraperConfig) -> list[ScraperResult]:
        from scraper.search_engine import is_cancelled

        max_results = config.get("max_results", 20)
        event_slugs = config.get("events", [])
        custom_urls = config.get("event_urls", [])
        results: list[ScraperResult] = []

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning("[Trade Shows] Playwright not installed — demo mode")
            return self.generate_demo_results(config)

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # Scrape hardcoded events
                for slug in event_slugs:
                    if is_cancelled() or len(results) >= max_results:
                        break
                    event = HARDCODED_EVENTS.get(slug)
                    if not event:
                        logger.warning(f"[Trade Shows] Unknown event slug: {slug}")
                        continue
                    entries = self._scrape_event(page, event, max_results - len(results))
                    results.extend(entries)

                # Scrape custom URLs (generic mode)
                for url in custom_urls:
                    if is_cancelled() or len(results) >= max_results:
                        break
                    entries = self._scrape_generic_url(page, url, max_results - len(results))
                    results.extend(entries)

                browser.close()
        except Exception as e:
            logger.error(f"[Trade Shows] Scraper error: {e}")

        return results[:max_results]

    def _scrape_event(self, page, event: dict, limit: int) -> list[ScraperResult]:
        """Scrape a hardcoded event's known exhibitor/speaker pages."""
        results = []
        event_name = event["name"]

        for url in event["urls"]:
            if len(results) >= limit:
                break
            try:
                page.goto(url, timeout=15000)
                page.wait_for_load_state("domcontentloaded", timeout=10000)
                entries = self._extract_exhibitors(page, url, f"Trade Show: {event_name}")
                results.extend(entries)
                logger.info(f"[Trade Shows] {event_name} ({url}): {len(entries)} entries")
            except Exception as e:
                logger.warning(f"[Trade Shows] Failed {url}: {e}")

        return results[:limit]

    def _scrape_generic_url(self, page, url: str, limit: int) -> list[ScraperResult]:
        """Attempt to extract exhibitor data from any URL. Returns empty + warning if 0 found."""
        try:
            page.goto(url, timeout=15000)
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            results = self._extract_exhibitors(page, url, "Trade Show: Custom")
            if not results:
                logger.warning(f"[Trade Shows] Generic URL returned 0 results: {url}")
            else:
                logger.info(f"[Trade Shows] Generic URL ({url}): {len(results)} entries")
            return results[:limit]
        except Exception as e:
            logger.warning(f"[Trade Shows] Generic URL failed {url}: {e}")
            return []

    def _extract_exhibitors(self, page, url: str, source_name: str) -> list[ScraperResult]:
        """Extract exhibitor/company data from common HTML patterns."""
        results = []
        selectors = [
            ".exhibitor-card", ".exhibitor", ".sponsor-card", ".sponsor",
            ".speaker-card", ".speaker", ".card", ".list-group-item",
            "table tbody tr", "dl",
        ]

        for selector in selectors:
            elements = page.query_selector_all(selector)
            if not elements:
                continue

            for el in elements:
                text = el.inner_text()
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                if len(lines) < 1:
                    continue

                # First line is typically company or person name
                company_name = lines[0]
                first_name = "Unknown"
                last_name = "Contact"

                # If first line looks like a person name (2-3 short words, no "Pty", "Ltd")
                name_parts = lines[0].split()
                if (len(name_parts) in (2, 3)
                    and not any(kw in lines[0].lower() for kw in ("pty", "ltd", "group", "inc"))):
                    first_name = name_parts[0]
                    last_name = " ".join(name_parts[1:])
                    company_name = lines[1] if len(lines) > 1 else "Unknown"

                # Try to find a link
                link = el.query_selector("a[href]")
                entry_url = url
                if link:
                    href = link.get_attribute("href")
                    if href and href.startswith("http"):
                        entry_url = href

                results.append({
                    "first_name": first_name,
                    "last_name": last_name,
                    "job_title": None,
                    "company_name": company_name,
                    "company_domain": None,
                    "linkedin_url": None,
                    "location_city": None,
                    "location_state": None,
                    "location_country": "AU",
                    "source_url": entry_url,
                    "source_name": source_name,
                })

            if results:
                break

        return results

    def generate_demo_results(self, config: ScraperConfig) -> list[ScraperResult]:
        from scraper.search_engine import generate_demo_data
        titles = [
            "Exhibitor Representative", "Sales Director", "Business Development Manager",
            "Technical Sales Engineer", "Regional Manager", "Marketing Director",
            "Booth Coordinator", "Product Specialist", "Account Manager",
        ]
        return generate_demo_data(
            keywords=config.get("keywords", []),
            max_results=config.get("max_results", 20),
            source_name="Trade Show: Demo Event",
            job_titles=titles,
            source_url_base="https://tradeshow.example.com",
        )
```

- [ ] **Step 3: Run tests, commit**

Run: `cd /home/kun/mastersales && python -m pytest tests/test_scrapers.py -v`
Expected: 12 PASSED

```bash
git add scraper/trade_shows.py tests/test_scrapers.py
git commit -m "feat: add trade show scraper with hardcoded events + generic URL mode"
```

---

## Task 10: Register All Scrapers

**Files:**
- Modify: `scraper/search_engine.py` (uncomment/enable `_register_scrapers`)

- [ ] **Step 1: Call `_register_scrapers()` at module level**

Add at bottom of `scraper/search_engine.py`:
```python
_register_scrapers()
```

- [ ] **Step 2: Run full test suite**

Run: `cd /home/kun/mastersales && python -m pytest tests/test_base_scraper.py tests/test_scrapers.py -v`
Expected: All PASSED

- [ ] **Step 3: Commit**

```bash
git add scraper/search_engine.py
git commit -m "feat: register all scrapers in source registry"
```

---

## Task 11: Update App Routes

**Files:**
- Modify: `app.py:583-755` (scraper routes section)

- [ ] **Step 1: Update scraper state variables** (line 585-586)

Replace:
```python
scraper_results: list[dict] = []
scraper_status: dict = {"running": False, "found": 0, "message": "Idle"}
```

With:
```python
import threading as _threading

scraper_results: list[dict] = []
scraper_status: dict = {"running": False, "sources": {}, "total_found": 0, "message": "Idle"}
_scraper_lock = _threading.Lock()
```

- [ ] **Step 2: Update `POST /scraper/start`** (line 600-643)

Rewrite to accept multi-source form data:
```python
@app.post("/scraper/start", response_class=HTMLResponse)
def scraper_start(
    request: Request,
    keywords: str = Form(""),
    location: str = Form("Australia"),
    max_results: int = Form(20),
    sources: str = Form("linkedin"),           # Comma-separated source slugs
    # Per-source credentials (all from localStorage)
    linkedin_email: str = Form(""),
    linkedin_password: str = Form(""),
    aca_username: str = Form(""),
    aca_password: str = Form(""),
    ampp_username: str = Form(""),
    ampp_password: str = Form(""),
    # Tender configs
    tenders_date_from: str = Form(""),
    tenders_date_to: str = Form(""),
    tenders_states: str = Form(""),            # Comma-separated
    # Trade show configs
    trade_show_events: str = Form(""),         # Comma-separated slugs
    trade_show_custom_url: str = Form(""),
):
```

Build credentials dict and source_configs dict from form fields.
Call `search_engine.run_scrape(sources, keywords, ...)` in a background thread.
Update `scraper_status` from the returned status dict.

- [ ] **Step 3: Add `POST /scraper/cancel`**

```python
@app.post("/scraper/cancel", response_class=HTMLResponse)
def scraper_cancel(request: Request):
    from scraper.search_engine import cancel_scrape
    cancel_scrape()
    scraper_status.update({"running": False, "message": "Cancelled by user"})
    return templates.TemplateResponse("partials/scraper_status.html", {
        "request": request,
        "scraper_status": scraper_status,
        "results": scraper_results,
    })
```

- [ ] **Step 4: Add source badge CSS helper**

Add to `app.py` (near the template setup):
```python
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
# Trade Shows and anything else get amber
_DEFAULT_BADGE = "bg-amber-100 text-amber-700"


def get_source_badge_css(source_name: str) -> str:
    """Return Tailwind CSS classes for a source badge."""
    for key, css in SOURCE_BADGE_CSS.items():
        if source_name.startswith(key):
            return css
    if "Trade Show" in source_name:
        return _DEFAULT_BADGE
    return "bg-gray-100 text-gray-700"
```

- [ ] **Step 5: Update `_add_scraper_result_to_db`** (find the function `_add_scraper_result_to_db`)

Change dedup logic (line 665-673):
```python
    existing = None
    if result.get("linkedin_url"):
        existing = db.query(Contact).filter(Contact.linkedin_url == result["linkedin_url"]).first()
    if not existing and result.get("first_name") and result.get("last_name") and result.get("company_name"):
        existing = db.query(Contact).filter(
            Contact.first_name == result["first_name"],
            Contact.last_name == result["last_name"],
            Contact.company.has(Company.company_name == result["company_name"]),
        ).first()
```

Update contact creation (line 692-706) to include new fields:
```python
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
```

Update company creation to include `company_domain`:
```python
    if not company:
        company = Company(
            company_name=result.get("company_name", ""),
            company_domain=result.get("company_domain"),
            company_industry=result.get("company_industry", ""),
            company_location=result.get("company_location", ""),
        )
```

- [ ] **Step 5: Run existing tests**

Run: `cd /home/kun/mastersales && python -m pytest tests/test_app.py -v`
Expected: All PASSED

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "feat: update routes for multi-source scraping with cancel support"
```

---

## Task 12: Tabbed Scraper UI

**Files:**
- Modify: `templates/scraper.html` (full rewrite of content block)

- [ ] **Step 1: Rewrite `templates/scraper.html`**

Key structure:

```html
{% block content %}
<div class="mb-6">
    <h2 class="text-2xl font-bold text-gray-900">Lead Sourcing</h2>
    <p class="text-sm text-gray-500 mt-1">Multi-source prospect discovery</p>
</div>

<!-- Search Form (wraps everything) -->
<form hx-post="/scraper/start" hx-target="#scraper-results" hx-swap="innerHTML">

    <!-- Shared Controls Card -->
    <div class="bg-white rounded-xl shadow-sm p-6 border border-gray-100 mb-4">
        <!-- Keywords, Location picker, Max Results — same as current -->
    </div>

    <!-- Source Tabs + Config (Alpine.js x-data) -->
    <div x-data="sourceManager()" class="bg-white rounded-xl shadow-sm border border-gray-100 mb-4">
        <!-- Tab bar: horizontal pills with status dots -->
        <div class="flex gap-1 p-3 border-b border-gray-100 overflow-x-auto">
            <template x-for="src in allSources" :key="src.slug">
                <button type="button" @click="activeTab = src.slug"
                    :class="activeTab === src.slug ? 'bg-navy text-white' : 'text-gray-600 hover:bg-gray-100'"
                    class="px-3 py-1.5 rounded-lg text-sm font-medium flex items-center gap-2 whitespace-nowrap transition-colors">
                    <span class="w-2 h-2 rounded-full" :class="dotClass(src.slug)"></span>
                    <span x-text="src.name"></span>
                </button>
            </template>
        </div>

        <!-- Per-source config panels (shown/hidden by activeTab) -->
        <!-- LinkedIn panel, ACA panel, AMPP panel, AU Tenders panel, NZ Tenders panel, Trade Shows panel -->
    </div>

    <!-- Source Selection Checkboxes + Submit -->
    <div class="bg-white rounded-xl shadow-sm p-4 border border-gray-100 mb-6">
        <div class="flex items-center justify-between">
            <div class="flex flex-wrap gap-3">
                <template x-for="src in allSources" :key="src.slug">
                    <label class="flex items-center gap-2 cursor-pointer">
                        <input type="checkbox" :value="src.slug" x-model="selectedSources"
                               class="w-4 h-4 rounded border-gray-300 text-navy focus:ring-navy">
                        <span class="text-sm" x-text="src.name"></span>
                    </label>
                </template>
            </div>
            <input type="hidden" name="sources" :value="selectedSources.join(',')">
            <button type="submit" :disabled="selectedSources.length === 0"
                class="px-6 py-2.5 bg-navy text-white rounded-lg text-sm font-medium hover:bg-navy-light transition-colors disabled:opacity-50">
                <span x-text="'Scrape ' + selectedSources.length + ' Source' + (selectedSources.length !== 1 ? 's' : '')"></span>
            </button>
        </div>
    </div>
</form>

<!-- Results -->
<div id="scraper-results">
    {% include "partials/scraper_status.html" %}
</div>

<script>
function sourceManager() {
    return {
        activeTab: 'linkedin',
        selectedSources: ['linkedin'],
        allSources: [
            { slug: 'linkedin', name: 'LinkedIn' },
            { slug: 'aca', name: 'ACA' },
            { slug: 'ampp', name: 'AMPP' },
            { slug: 'tenders_au', name: 'AU Tenders' },
            { slug: 'tenders_nz', name: 'NZ Tenders' },
            { slug: 'trade_shows', name: 'Trade Shows' },
        ],
        dotClass(slug) {
            // Check localStorage for configured creds
            if (slug === 'linkedin') return localStorage.getItem('li_email') ? 'bg-green-400' : 'bg-gray-300';
            if (slug === 'aca') return localStorage.getItem('aca_username') ? 'bg-green-400' : 'bg-gray-300';
            if (slug === 'ampp') return localStorage.getItem('ampp_username') ? 'bg-green-400' : 'bg-gray-300';
            return 'bg-green-400'; // Public sources always "configured"
        }
    };
}

// Per-source localStorage load/save (same pattern as existing LinkedIn creds)
// linkedin, aca, ampp credential management functions
</script>
{% endblock %}
```

Each per-source config panel follows the existing LinkedIn credential pattern: collapsible section, localStorage persistence, "Remember on this device" checkbox.

For AU Tenders panel: date range inputs + state checkboxes (QLD, NSW, VIC, WA, All).
For Trade Shows panel: hardcoded event checkboxes + custom URL text input.

- [ ] **Step 2: Commit**

```bash
git add templates/scraper.html
git commit -m "feat: tabbed multi-source scraper UI with source selection"
```

---

## Task 13: Per-Source Status + Results Table

**Files:**
- Modify: `templates/partials/scraper_status.html`
- Modify: `templates/partials/scraper_row_added.html`

- [ ] **Step 1: Rewrite `scraper_status.html`**

Key changes:
1. Per-source status bar (replaces single spinner):
```html
{% if scraper_status.running %}
<div class="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-6" hx-get="/scraper/status" hx-trigger="every 2s" hx-swap="outerHTML">
    <div class="flex flex-wrap gap-3">
        {% for slug, src_status in scraper_status.get('sources', {}).items() %}
        <div class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white border border-gray-200">
            {% if src_status.status == 'running' %}
            <svg class="animate-spin h-3.5 w-3.5 text-blue-500">...</svg>
            {% elif src_status.status == 'complete' %}
            <span class="text-green-500">&#10003;</span>
            {% elif src_status.status == 'error' %}
            <span class="text-red-500">&#10007;</span>
            {% endif %}
            <span class="text-xs font-medium text-gray-700">{{ slug }}</span>
            <span class="text-xs text-gray-500">{{ src_status.found }} found</span>
        </div>
        {% endfor %}
    </div>
    <!-- Cancel button -->
    <button hx-post="/scraper/cancel" hx-target="#scraper-results" hx-swap="innerHTML"
            class="mt-2 px-3 py-1 text-xs text-red-600 hover:text-red-800">Cancel</button>
</div>
{% endif %}
```

2. Results table with Source column:
- Add `<th>Source</th>` header
- Add source badge cell per row:
The badge CSS comes from the `get_source_badge_css()` helper defined in Task 11. Pass it to the template context when rendering results:

```python
# In the scraper_status_check and scraper_page routes, add to context:
"get_source_badge_css": get_source_badge_css,
```

Then in the template:
```html
<td class="px-4 py-3">
    <span class="px-2 py-0.5 rounded text-xs font-medium {{ get_source_badge_css(result.get('source_name', '')) }}">
        {{ result.get('source_name', 'Unknown')[:12] }}
    </span>
</td>
```

3. Source filter dropdown above table:
```html
<div x-data="{ sourceFilter: 'all' }" class="mb-2">
    <select x-model="sourceFilter" class="text-sm border-gray-300 rounded-lg">
        <option value="all">All Sources</option>
        <!-- Dynamic options from results -->
    </select>
</div>
```

4. Add "DEMO" badge when result has demo source_url.

- [ ] **Step 2: Update `scraper_row_added.html`**

Add source badge column between Location and Action columns:
```html
<td class="px-4 py-3">
    <span class="px-2 py-0.5 rounded text-xs font-medium {{ source_badge_css }}">{{ source_name }}</span>
</td>
```

Update `app.py` function `scraper_add_lead` to pass badge data to the template:
```python
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
```

- [ ] **Step 3: Commit**

```bash
git add templates/partials/scraper_status.html templates/partials/scraper_row_added.html app.py
git commit -m "feat: per-source status bars, source column, and filter dropdown"
```

---

## Task 14: Integration Test

**Files:**
- Test: `tests/test_base_scraper.py` (add end-to-end test)

- [ ] **Step 1: Write integration test with demo mode**

```python
def test_full_scrape_demo_mode():
    """End-to-end: run all scrapers in demo mode, verify dedup and output format."""
    from scraper.search_engine import run_scrape, _register_scrapers
    _register_scrapers()

    results, status = run_scrape(
        sources=["linkedin", "aca", "ampp", "tenders_au", "tenders_nz", "trade_shows"],
        keywords=["steel", "corrosion"],
        location="Australia",
        max_results=5,
        credentials={},  # No creds = demo mode for all
        source_configs={
            "tenders_au": {"date_from": "2025-01-01", "date_to": "2026-01-01"},
            "tenders_nz": {"date_from": "2025-01-01", "date_to": "2026-01-01"},
            "trade_shows": {"events": ["aca_conf"]},
        },
    )

    assert len(results) > 0
    assert not status["running"]

    # All results have required fields
    for r in results:
        assert r["first_name"]
        assert r["last_name"]
        assert r["company_name"]
        assert r["source_name"]

    # Multiple sources represented
    sources_seen = {r["source_name"].split(",")[0].strip() for r in results}
    assert len(sources_seen) >= 3  # At least 3 different sources produced results
```

- [ ] **Step 2: Run full test suite**

Run: `cd /home/kun/mastersales && python -m pytest tests/ -v --ignore=tests/__pycache__`
Expected: All PASSED

- [ ] **Step 3: Commit**

```bash
git add tests/test_base_scraper.py
git commit -m "test: add integration test for multi-source demo mode"
```

---

## Task 15: Final Cleanup + Smoke Test

- [ ] **Step 1: Remove old demo data from `search_engine.py`**

The old `_generate_demo_results()`, `_FIRST_NAMES`, `_LAST_NAMES`, `_JOB_TITLES`, `_COMPANIES` lists are now replaced by `generate_demo_data()` and `DEMO_*` constants. Remove the old functions if they're still present.

- [ ] **Step 2: Verify the app starts**

Run: `cd /home/kun/mastersales && python -c "from app import app; print('App loaded OK')"`
Expected: `App loaded OK`

- [ ] **Step 3: Run full test suite**

Run: `cd /home/kun/mastersales && python -m pytest tests/ -v --ignore=tests/__pycache__`
Expected: All PASSED

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: cleanup old demo data, verify multi-source scraper integration"
```
