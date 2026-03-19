import logging
import time
import random
import threading
from scraper.base import BaseScraper, ScraperConfig, ScraperResult

logger = logging.getLogger("mastersales.scraper")
SCRAPERS: dict[str, type[BaseScraper]] = {}
_lock = threading.Lock()
_cancel_event = threading.Event()
_browser_semaphore = threading.Semaphore(5)


# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------

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
    ("CSBP Chemicals", "Kwinana", "WA", "AU"),
    ("Worley Parsons", "Perth", "WA", "AU"),
    ("Fletcher Steel NZ", "Hamilton", "Waikato", "NZ"),
    ("Austal Ships", "Henderson", "WA", "AU"),
    ("Transfield Services", "Sydney", "NSW", "AU"),
    ("John Holland Group", "Melbourne", "VIC", "AU"),
    ("Pilbara Minerals", "Pilgangoora", "WA", "AU"),
    ("South32 Worsley Alumina", "Collie", "WA", "AU"),
    ("Steel & Tube NZ", "Lower Hutt", "Wellington", "NZ"),
    ("Valmec Engineering", "Welshpool", "WA", "AU"),
]

DEMO_JOB_TITLES = [
    "Steel Fabrication Manager", "Corrosion Engineer", "Maintenance Director",
    "Shipyard Operations Manager", "Procurement Specialist - Coatings",
    "Quality Control Manager", "Site Engineer", "Workshop Foreman",
    "Rust Prevention Specialist", "Materials Engineer", "Fabrication Supervisor",
    "Protective Coatings Inspector", "Plant Manager", "Supply Chain Manager",
    "Underground Mining Engineer", "Structural Engineer", "Asset Integrity Manager",
    "Project Engineer - Steel Structures", "Surface Preparation Supervisor",
    "Welding Inspector", "Operations Manager", "Workshop Manager",
    "Coating Application Technician", "Safety & Compliance Manager",
    "Procurement Manager - Industrial Coatings", "Production Supervisor",
    "Mining Operations Engineer", "Civil & Structural Lead", "Fleet Maintenance Manager",
    "Infrastructure Project Manager", "HSE Manager", "Marine Coatings Specialist",
    "Blast & Paint Supervisor", "Reliability Engineer", "Warehouse & Logistics Manager",
    "Technical Sales Manager - Coatings", "Workshop Superintendent",
    "Pipeline Integrity Engineer", "Contracts Manager", "Plant Maintenance Planner",
]


def generate_demo_data(
    keywords: list[str],
    max_results: int,
    source_name: str,
    job_titles: list[str] | None = None,
    source_url_base: str = "https://example.com",
) -> list[ScraperResult]:
    """Generate realistic demo scraping results. Shared by all scrapers."""
    seed = hash(tuple(sorted(keywords)) + (source_name,)) & 0xFFFFFFFF
    rng = random.Random(seed)

    titles = job_titles or DEMO_JOB_TITLES
    results: list[ScraperResult] = []
    used_names: set[tuple[str, str]] = set()

    for _ in range(max_results):
        for _attempt in range(50):
            first = rng.choice(DEMO_FIRST_NAMES)
            last = rng.choice(DEMO_LAST_NAMES)
            if (first, last) not in used_names:
                used_names.add((first, last))
                break

        title = rng.choice(titles)
        company, city, state, country = rng.choice(DEMO_COMPANIES)
        slug = f"{first.lower()}-{last.lower().replace(chr(39), '')}-{rng.randint(100, 999)}"

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
            "source_url": f"{source_url_base}/{slug}",
            "source_name": source_name,
        })

    return results


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _dedup_key(r: dict) -> str:
    return f"{r['first_name'].lower().strip()}|{r['last_name'].lower().strip()}|{r['company_name'].lower().strip()}"


def _richness(r: dict) -> int:
    """Count non-None optional fields."""
    optional = [
        "job_title", "company_domain", "linkedin_url",
        "location_city", "location_state", "location_country", "source_url",
    ]
    return sum(1 for f in optional if r.get(f) is not None)


def dedup_results(results: list[dict]) -> list[dict]:
    """Cross-source dedup: keep richer record, combine source_names."""
    seen: dict[str, dict] = {}
    for r in results:
        key = _dedup_key(r)
        if key in seen:
            existing = seen[key]
            # Combine source names
            existing_sources = set(existing["source_name"].split(", "))
            new_sources = set(r["source_name"].split(", "))
            combined_sources = existing_sources | new_sources

            # Keep the richer record
            if _richness(r) > _richness(existing):
                r["source_name"] = ", ".join(sorted(combined_sources))
                seen[key] = r
            else:
                existing["source_name"] = ", ".join(sorted(combined_sources))
        else:
            seen[key] = r
    return list(seen.values())


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def cancel_scrape() -> None:
    """Signal all running scrapers to stop."""
    _cancel_event.set()


def is_cancelled() -> bool:
    """Check whether a cancellation has been requested."""
    return _cancel_event.is_set()


def run_scrape(
    sources: list[str],
    keywords: list[str],
    location: str = "Australia",
    max_results: int = 20,
    credentials: dict | None = None,
    source_configs: dict | None = None,
) -> tuple[list[ScraperResult], dict]:
    """Run scrape across multiple sources in parallel.

    Returns (deduped_results, status_dict).
    """
    credentials = credentials or {}
    source_configs = source_configs or {}
    _cancel_event.clear()

    status: dict = {
        "running": True,
        "sources": {},
        "total_found": 0,
    }

    all_results: list[dict] = []

    def _run_source(slug: str) -> None:
        scraper_cls = SCRAPERS.get(slug)
        if scraper_cls is None:
            with _lock:
                status["sources"][slug] = {"status": "error", "found": 0}
            return

        scraper = scraper_cls()

        config: ScraperConfig = {
            "keywords": keywords,
            "location": location,
            "max_results": max_results,
            **(source_configs.get(slug) or {}),
        }

        # If auth required but no creds, use demo results
        needs_auth = scraper.requires_auth
        has_creds = bool(credentials.get(slug))
        if needs_auth and not has_creds:
            config["credentials"] = {}
        else:
            config["credentials"] = credentials.get(slug, {})

        with _lock:
            status["sources"][slug] = {"status": "running", "found": 0}

        acquired = False
        try:
            if scraper.uses_browser:
                _browser_semaphore.acquire()
                acquired = True

            if needs_auth and not has_creds:
                logger.info("[%s] No credentials provided — skipping (demo disabled)", slug)
                results = []
            else:
                results = scraper.scrape(config)

            with _lock:
                all_results.extend(results)
                status["sources"][slug] = {"status": "complete", "found": len(results)}
                status["total_found"] = sum(
                    s["found"] for s in status["sources"].values()
                )
        except Exception as e:
            logger.exception("Scraper %s failed: %s", slug, e)
            with _lock:
                status["sources"][slug] = {"status": "error", "found": 0}
        finally:
            if acquired:
                _browser_semaphore.release()

    threads: list[threading.Thread] = []
    for slug in sources:
        t = threading.Thread(target=_run_source, args=(slug,), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    deduped = dedup_results(all_results)

    # Fair merge: guarantee each source gets at least MIN_PER_SOURCE results,
    # then fill remaining slots with leftover results round-robin.
    MIN_PER_SOURCE = 5
    if len(deduped) > max_results and len(sources) > 1:
        deduped = _fair_merge(deduped, sources, max_results, MIN_PER_SOURCE)

    with _lock:
        status["running"] = False
        status["total_found"] = len(deduped)

    return deduped, status


def _fair_merge(
    results: list[dict],
    sources: list[str],
    max_results: int,
    min_per_source: int,
) -> list[dict]:
    """Merge results ensuring each source gets at least min_per_source slots.

    1. Group results by primary source name
    2. Take up to min_per_source from each source
    3. Fill remaining slots with leftovers round-robin
    """
    # Group by primary source (first source name before comma)
    by_source: dict[str, list[dict]] = {}
    for r in results:
        primary = r["source_name"].split(",")[0].strip()
        # Map sub-sources to parent (e.g. "AusTender" -> "tenders_au")
        matched_slug = None
        for slug in sources:
            scraper_cls = SCRAPERS.get(slug)
            if scraper_cls and primary.startswith(scraper_cls.name.split()[0]):
                matched_slug = slug
                break
        key = matched_slug or primary
        by_source.setdefault(key, []).append(r)

    # Phase 1: take min_per_source from each source that has results
    merged = []
    remaining_by_source: dict[str, list[dict]] = {}
    for key, items in by_source.items():
        take = min(min_per_source, len(items))
        merged.extend(items[:take])
        if len(items) > take:
            remaining_by_source[key] = items[take:]

    # Phase 2: fill remaining slots round-robin from leftovers
    slots_left = max_results - len(merged)
    if slots_left > 0 and remaining_by_source:
        source_keys = list(remaining_by_source.keys())
        idx = 0
        while slots_left > 0 and remaining_by_source:
            key = source_keys[idx % len(source_keys)]
            if remaining_by_source[key]:
                merged.append(remaining_by_source[key].pop(0))
                slots_left -= 1
            if not remaining_by_source[key]:
                source_keys.remove(key)
                if not source_keys:
                    break
            else:
                idx += 1

    return merged[:max_results]


# ---------------------------------------------------------------------------
# Scraper registration (called in Task 10 after all scrapers exist)
# ---------------------------------------------------------------------------

def _register_scrapers():
    global SCRAPERS
    from scraper.linkedin import LinkedInScraper
    from scraper.aca import ACAScraper
    from scraper.ampp import AMPPScraper
    from scraper.tenders_au import AusTenderScraper
    from scraper.tenders_nz import GETSScraper
    from scraper.trade_shows import TradeShowScraper
    SCRAPERS = {
        "linkedin": LinkedInScraper, "aca": ACAScraper, "ampp": AMPPScraper,
        "tenders_au": AusTenderScraper, "tenders_nz": GETSScraper, "trade_shows": TradeShowScraper,
    }


_register_scrapers()
