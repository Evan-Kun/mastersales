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
        "search_path": "/cn/search",
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
            logger.warning("[AU Tenders] Playwright not installed — cannot scrape")
            return []

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
        # Use specialised path for AusTender Contract Notices
        if portal.get("name") == "AusTender":
            return self._scrape_austender_cn(page, portal, keywords, limit)
        return self._scrape_generic_portal(page, portal, keywords, limit)

    def _scrape_austender_cn(
        self, page, portal: dict, keywords: list[str], limit: int
    ) -> list[ScraperResult]:
        """Scrape AusTender Contract Notices search (/cn/search).

        The search is a 2-step form:
          Step 1 — fill criteria (keyword, date range, supplier, etc.)
          Step 2 — view results table
        """
        results: list[ScraperResult] = []
        keyword_str = " ".join(keywords[:3])
        url = f"{portal['base_url']}{portal['search_path']}"

        try:
            page.goto(url, timeout=25000)
            page.wait_for_load_state("domcontentloaded", timeout=15000)

            # Fill Keyword field (labelled "Keyword")
            if keyword_str.strip():
                try:
                    page.get_by_role("textbox", name="Keyword").fill(keyword_str)
                except Exception:
                    # Fallback to CSS selectors
                    for sel in ['input[name="keyword"]', 'input[name="Keyword"]',
                                '#keyword', 'input[type="text"]']:
                        try:
                            el = page.query_selector(sel)
                            if el:
                                el.fill(keyword_str)
                                break
                        except Exception:
                            continue

            # Fill date range — last 12 months in DD-MMM-YYYY format
            from_date = (datetime.now() - timedelta(days=365)).strftime("%d-%b-%Y")
            to_date = datetime.now().strftime("%d-%b-%Y")
            try:
                page.get_by_role("textbox", name="from").first.fill(from_date)
            except Exception:
                for sel in ['input[name="fromDate"]', 'input[name="publishedFrom"]']:
                    try:
                        el = page.query_selector(sel)
                        if el:
                            el.fill(from_date)
                            break
                    except Exception:
                        continue
            try:
                page.get_by_role("textbox", name="to").first.fill(to_date)
            except Exception:
                for sel in ['input[name="toDate"]', 'input[name="publishedTo"]']:
                    try:
                        el = page.query_selector(sel)
                        if el:
                            el.fill(to_date)
                            break
                    except Exception:
                        continue

            # Click Search button
            submitted = False
            try:
                page.get_by_role("button", name="Search").click()
                submitted = True
            except Exception:
                for sel in ['button[type="submit"]', 'input[type="submit"]',
                            'button:has-text("Search")', '#searchButton']:
                    try:
                        btn = page.query_selector(sel)
                        if btn:
                            btn.click()
                            submitted = True
                            break
                    except Exception:
                        continue

            if submitted:
                # Wait for Step 2 results page to load
                page.wait_for_load_state("networkidle", timeout=20000)

            # Extract results from the CN results table
            results = self._extract_tender_results(page, portal)

        except Exception as e:
            logger.warning(f"[AU Tenders] AusTender CN scrape error: {e}")

        return results[:limit]

    def _scrape_generic_portal(
        self, page, portal: dict, keywords: list[str], limit: int
    ) -> list[ScraperResult]:
        """Scrape a generic state tender portal."""
        results = []
        keyword_str = " ".join(keywords[:3])
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
