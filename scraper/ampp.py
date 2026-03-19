import logging
from scraper.base import BaseScraper, ScraperConfig, ScraperResult

logger = logging.getLogger("mastersales.scraper.ampp")


class AMPPScraper(BaseScraper):
    name = "AMPP"
    slug = "ampp"
    requires_auth = False
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
                creds = config.get("credentials", {})
                if creds.get("username") and creds.get("password") and len(results) < max_results:
                    try:
                        page.goto("https://www.ampp.org/login", timeout=15000)
                        page.fill('input[name="username"], input[type="email"]', creds["username"])
                        page.fill('input[type="password"]', creds["password"])
                        page.click('button[type="submit"], input[type="submit"]')
                        page.wait_for_load_state("domcontentloaded", timeout=10000)
                        page.goto("https://www.ampp.org/community/member-directory", timeout=15000)
                        entries = self._extract_people_from_page(page, "https://www.ampp.org/community/member-directory")
                        results.extend(entries)
                    except Exception as e:
                        logger.warning(f"[AMPP] Member directory login failed: {e}")
                browser.close()
        except Exception as e:
            logger.error(f"[AMPP] Scraper error: {e}")
        return results[:max_results]

    def _extract_people_from_page(self, page, url: str) -> list[ScraperResult]:
        results = []
        selectors = [".person-card", ".speaker-card", ".member-item", "table tbody tr", ".card", ".profile-item"]
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
                    "first_name": name_parts[0], "last_name": " ".join(name_parts[1:]),
                    "job_title": lines[1] if len(lines) > 1 else None,
                    "company_name": lines[2] if len(lines) > 2 else "Unknown",
                    "company_domain": None, "linkedin_url": None,
                    "location_city": None, "location_state": None, "location_country": "AU",
                    "source_url": url, "source_name": "AMPP",
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
