import time
import random
from playwright.sync_api import sync_playwright
from config import settings


class LinkedInScraper:
    """Playwright-based LinkedIn scraper for people search."""

    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.browser = None
        self.page = None

    def _random_delay(self):
        time.sleep(random.uniform(settings.scrape_delay_min, settings.scrape_delay_max))

    def _login(self):
        """Log into LinkedIn."""
        self.page.goto("https://www.linkedin.com/login")
        self._random_delay()

        self.page.fill('#username', self.email)
        self.page.fill('#password', self.password)
        self.page.click('button[type="submit"]')
        self._random_delay()

        # Wait for login to complete
        self.page.wait_for_url("**/feed/**", timeout=30000)

    def search_people(self, keywords: list[str], location: str, max_results: int = 20) -> list[dict]:
        """Search LinkedIn for people matching keywords and location."""
        results = []

        with sync_playwright() as p:
            self.browser = p.chromium.launch(headless=True)
            context = self.browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            self.page = context.new_page()

            try:
                self._login()

                keyword_str = " ".join(keywords)
                search_url = f"https://www.linkedin.com/search/results/people/?keywords={keyword_str}&origin=GLOBAL_SEARCH_HEADER"
                self.page.goto(search_url)
                self._random_delay()

                page_num = 1
                while len(results) < max_results:
                    # Wait for search results
                    self.page.wait_for_selector('.search-results-container', timeout=10000)
                    self._random_delay()

                    # Extract results from current page
                    cards = self.page.query_selector_all('.entity-result__item')
                    if not cards:
                        cards = self.page.query_selector_all('[data-chameleon-result-urn]')

                    for card in cards:
                        if len(results) >= max_results:
                            break

                        try:
                            person = self._extract_person_from_card(card)
                            if person:
                                results.append(person)
                        except Exception:
                            continue

                    # Check for next page
                    next_btn = self.page.query_selector('button[aria-label="Next"]')
                    if not next_btn or not next_btn.is_enabled() or len(results) >= max_results:
                        break

                    next_btn.click()
                    self._random_delay()
                    page_num += 1

            finally:
                self.browser.close()

        return results

    def _extract_person_from_card(self, card) -> dict | None:
        """Extract person data from a LinkedIn search result card."""
        name_el = card.query_selector('.entity-result__title-text a span[aria-hidden="true"]')
        if not name_el:
            name_el = card.query_selector('.entity-result__title-text a')
        if not name_el:
            return None

        full_name = name_el.inner_text().strip()
        parts = full_name.split(" ", 1)
        first_name = parts[0] if parts else ""
        last_name = parts[1] if len(parts) > 1 else ""

        title_el = card.query_selector('.entity-result__primary-subtitle')
        job_title = title_el.inner_text().strip() if title_el else ""

        location_el = card.query_selector('.entity-result__secondary-subtitle')
        location_text = location_el.inner_text().strip() if location_el else ""

        link_el = card.query_selector('.entity-result__title-text a')
        linkedin_url = link_el.get_attribute('href') if link_el else ""
        if linkedin_url and '?' in linkedin_url:
            linkedin_url = linkedin_url.split('?')[0]

        # Parse location
        location_city = ""
        location_state = ""
        location_country = "AU"
        if location_text:
            loc_parts = [p.strip() for p in location_text.split(",")]
            if loc_parts:
                location_city = loc_parts[0]
            if len(loc_parts) > 1:
                location_state = loc_parts[1]
            if "New Zealand" in location_text or "NZ" in location_text:
                location_country = "NZ"

        return {
            "first_name": first_name,
            "last_name": last_name,
            "job_title": job_title,
            "linkedin_url": linkedin_url,
            "location_city": location_city,
            "location_state": location_state,
            "location_country": location_country,
            "company_name": "",  # Would need to visit profile for this
        }
