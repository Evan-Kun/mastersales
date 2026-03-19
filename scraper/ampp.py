import logging
import re
from urllib.parse import urlparse
from scraper.base import BaseScraper, ScraperConfig, ScraperResult

logger = logging.getLogger("mastersales.scraper.ampp")

DIRECTORY_URL = "https://profile.ampp.org/corporatedirectory"

HONORIFICS = {"mr.", "mrs.", "ms.", "dr.", "prof.", "mr", "mrs", "ms", "dr", "prof"}

# Common countries that appear at the end of AMPP addresses
COUNTRIES = {
    "United States", "Australia", "Canada", "China", "United Kingdom",
    "Germany", "France", "India", "Japan", "South Korea", "Brazil",
    "Mexico", "Saudi Arabia", "United Arab Emirates", "Qatar", "Kuwait",
    "Oman", "Bahrain", "Singapore", "Malaysia", "Indonesia", "Thailand",
    "Norway", "Netherlands", "Italy", "Spain", "Turkey", "Egypt",
    "South Africa", "Nigeria", "New Zealand", "Philippines", "Vietnam",
    "Colombia", "Chile", "Argentina", "Peru", "Trinidad and Tobago",
    "Iraq", "Iran", "Pakistan", "Bangladesh", "Sri Lanka", "Belgium",
    "Sweden", "Denmark", "Finland", "Poland", "Czech Republic",
    "Austria", "Switzerland", "Ireland", "Scotland", "Portugal",
    "Greece", "Romania", "Hungary", "Israel", "Jordan", "Lebanon",
}

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}


def _parse_contact_name(full_name: str) -> tuple[str, str]:
    """Parse a contact name, stripping honorifics, returning (first, last)."""
    parts = full_name.strip().split()
    # Strip leading honorifics
    while parts and parts[0].lower().rstrip(".") + "." in HONORIFICS:
        parts.pop(0)
    if len(parts) == 0:
        return ("Unknown", "Unknown")
    if len(parts) == 1:
        return (parts[0], "Unknown")
    return (parts[0], " ".join(parts[1:]))


def _parse_address(address: str) -> tuple[str | None, str | None, str | None]:
    """Parse address text into (city, state, country)."""
    if not address or not address.strip():
        return (None, None, None)

    country = None
    state = None
    city = None

    # Normalize whitespace
    addr = " ".join(address.split())

    # Check for known country at the end
    for c in COUNTRIES:
        if addr.endswith(c):
            country = c
            addr = addr[: -len(c)].rstrip(", ")
            break

    # Try to find state abbreviation (US) — typically after last comma
    parts = [p.strip() for p in addr.split(",")]
    if parts:
        last_part = parts[-1].strip()
        # Check for "STATE ZIP" or just "STATE"
        tokens = last_part.split()
        if tokens:
            candidate = tokens[0].upper()
            if candidate in US_STATES:
                state = candidate
                if not country:
                    country = "United States"
                # City is the part before the state
                if len(parts) >= 2:
                    city = parts[-2].strip()
            else:
                # Last part might be the city itself
                if len(parts) >= 2:
                    city = parts[-2].strip()
                elif len(parts) == 1:
                    city = parts[0].strip()

    return (city, state, country)


def _extract_domain(url: str) -> str | None:
    """Extract domain from a URL."""
    if not url:
        return None
    try:
        parsed = urlparse(url if "://" in url else f"http://{url}")
        domain = parsed.hostname
        if domain:
            # Strip www.
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
    except Exception:
        pass
    return None


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
            logger.warning("[AMPP] Playwright not installed — cannot scrape")
            return []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # Navigate to the public corporate directory
                page.goto(DIRECTORY_URL, timeout=60000)
                page.wait_for_load_state("domcontentloaded", timeout=30000)

                # Wait for the table to appear
                page.wait_for_selector("table", timeout=30000)

                page_num = 0
                while len(results) < max_results:
                    if is_cancelled():
                        break

                    page_num += 1
                    new_entries = self._extract_from_table(page)
                    if not new_entries:
                        logger.info(f"[AMPP] Page {page_num}: no entries found, stopping")
                        break

                    results.extend(new_entries)
                    logger.info(f"[AMPP] Page {page_num}: found {len(new_entries)} entries (total: {len(results)})")

                    if len(results) >= max_results:
                        break

                    # Try to click Next for pagination
                    if not self._go_to_next_page(page):
                        logger.info("[AMPP] No more pages available")
                        break

                browser.close()
        except Exception as e:
            logger.error(f"[AMPP] Scraper error: {e}")
            if not results:
                logger.warning("[AMPP] Scraper failed — no results")


        return results[:max_results]

    def _extract_from_table(self, page) -> list[ScraperResult]:
        """Extract company/contact data from the corporate directory table."""
        results = []

        # The table uses <rowgroup> and <row> elements, or standard tr/td
        # Try multiple selectors for rows
        rows = page.query_selector_all("table tr")
        if not rows:
            rows = page.query_selector_all("table row")
        if not rows:
            rows = page.query_selector_all("table tbody tr")

        for row in rows:
            try:
                cells = row.query_selector_all("td")
                if not cells:
                    cells = row.query_selector_all("cell")
                if len(cells) < 5:
                    continue  # Skip header rows or malformed rows

                # Cell 0: Company Name
                company_name = (cells[0].inner_text() or "").strip()
                if not company_name:
                    continue

                # Cell 1: Address
                address_text = (cells[1].inner_text() or "").strip()
                city, state, country = _parse_address(address_text)

                # Cell 2: Phone (not used in ScraperResult but logged)
                # phone = (cells[2].inner_text() or "").strip()

                # Cell 3: Website — extract href from link or text
                website = None
                website_link = cells[3].query_selector("a")
                if website_link:
                    website = website_link.get_attribute("href")
                if not website:
                    website = (cells[3].inner_text() or "").strip()
                company_domain = _extract_domain(website)

                # Cell 4: Primary Contact Name
                contact_name = (cells[4].inner_text() or "").strip()
                if not contact_name:
                    continue
                first_name, last_name = _parse_contact_name(contact_name)

                # Cell 5: Primary Contact Email (useful but not in ScraperResult)
                # email = None
                # if len(cells) > 5:
                #     email_link = cells[5].query_selector("a")
                #     if email_link:
                #         href = email_link.get_attribute("href") or ""
                #         if href.startswith("mailto:"):
                #             email = href[7:]

                # Cell 6: Membership Level (skip)

                results.append({
                    "first_name": first_name,
                    "last_name": last_name,
                    "job_title": "Primary Contact",
                    "company_name": company_name,
                    "company_domain": company_domain,
                    "linkedin_url": None,
                    "location_city": city,
                    "location_state": state,
                    "location_country": country,
                    "source_url": DIRECTORY_URL,
                    "source_name": "AMPP",
                })
            except Exception as e:
                logger.debug(f"[AMPP] Error parsing row: {e}")
                continue

        return results

    def _go_to_next_page(self, page) -> bool:
        """Click the 'Next' pagination link. Returns True if successful."""
        try:
            # Look for a "Next" link in the pagination
            next_link = page.query_selector("a:has-text('Next')")
            if not next_link:
                next_link = page.query_selector("a:text-is('Next')")
            if not next_link:
                # Try finding by aria-label or title
                next_link = page.query_selector("[aria-label='Next']")
            if not next_link:
                next_link = page.query_selector("a.next, .pagination a:has-text('Next')")

            if not next_link:
                return False

            # Check if the Next link is disabled
            classes = next_link.get_attribute("class") or ""
            if "disabled" in classes:
                return False

            next_link.click()
            # Wait for table to reload
            page.wait_for_load_state("networkidle", timeout=10000)
            page.wait_for_selector("table", timeout=10000)
            # Small delay to ensure content is updated
            page.wait_for_timeout(500)
            return True
        except Exception as e:
            logger.debug(f"[AMPP] Pagination error: {e}")
            return False

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
