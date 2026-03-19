import logging
from scraper.base import BaseScraper, ScraperConfig, ScraperResult

logger = logging.getLogger("mastersales.scraper.aca")


class ACAScraper(BaseScraper):
    name = "ACA"
    slug = "aca"
    requires_auth = False
    uses_browser = True
    credential_fields = [
        {"key": "username", "label": "ACA Username", "type": "text"},
        {"key": "password", "label": "ACA Password", "type": "password"},
    ]

    def scrape(self, config: ScraperConfig) -> list[ScraperResult]:
        from scraper.search_engine import is_cancelled
        max_results = config.get("max_results", 20)
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
                        entries = self._extract_people_from_page(page, url)
                        results.extend(entries)
                        logger.info(f"[ACA] {url}: found {len(entries)} entries")
                    except Exception as e:
                        logger.warning(f"[ACA] Failed to scrape {url}: {e}")
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
        results = []
        selectors = [".person-card", ".speaker-card", ".member-item", ".committee-member", "article.person", "table tbody tr", ".card"]
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
                first_name = name_parts[0]
                last_name = " ".join(name_parts[1:])
                job_title = lines[1] if len(lines) > 1 else None
                company = lines[2] if len(lines) > 2 else "Unknown"
                results.append({
                    "first_name": first_name, "last_name": last_name, "job_title": job_title,
                    "company_name": company, "company_domain": None, "linkedin_url": None,
                    "location_city": None, "location_state": None, "location_country": "AU",
                    "source_url": url, "source_name": "ACA",
                })
            if results:
                break
        return results

    def _login(self, page, username: str, password: str):
        page.goto("https://www.corrosion.com.au/login", timeout=15000)
        page.fill('input[name="username"], input[type="email"]', username)
        page.fill('input[type="password"]', password)
        page.click('button[type="submit"], input[type="submit"]')
        page.wait_for_load_state("domcontentloaded", timeout=10000)

    def _scrape_member_directory(self, page, max_results: int) -> list[ScraperResult]:
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
