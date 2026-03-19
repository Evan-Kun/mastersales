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
