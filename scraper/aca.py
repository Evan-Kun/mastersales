import logging
import re
from urllib.parse import urlparse

from scraper.base import BaseScraper, ScraperConfig, ScraperResult

logger = logging.getLogger("mastersales.scraper.aca")

DIRECTORY_URL = "https://www.corrosion.com.au/corrosion-experts/corrosion-control-directory/"

# Australian state abbreviations
AU_STATES = {"NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT"}


def _parse_name(full_name: str) -> tuple[str, str]:
    """Split a full name into (first_name, last_name)."""
    parts = full_name.strip().split()
    if len(parts) == 0:
        return ("", "")
    if len(parts) == 1:
        return (parts[0], "")
    return (parts[0], " ".join(parts[1:]))


def _parse_address(address_text: str) -> dict:
    """Extract city, state, country from an Australian/NZ address string."""
    city = None
    state = None
    country = None

    text = address_text.strip()

    # Detect country
    if "new zealand" in text.lower() or "nz" in text.upper().split():
        country = "NZ"
    elif "australia" in text.lower():
        country = "AU"
    else:
        country = "AU"  # default for ACA directory

    # Remove "Australia" / "New Zealand" from end for easier parsing
    cleaned = re.sub(r',?\s*(Australia|New Zealand)\s*$', '', text, flags=re.IGNORECASE).strip()

    # Try to find state abbreviation and postcode pattern like "NSW 2100" or "WA 6004"
    state_match = re.search(r'\b(' + '|'.join(AU_STATES) + r')\s*\d{4}\b', cleaned)
    if state_match:
        state = state_match.group(1)

    if not state:
        # Try state without postcode
        state_match = re.search(r'\b(' + '|'.join(AU_STATES) + r')\b', cleaned)
        if state_match:
            state = state_match.group(1)

    # Try to extract city: the comma-separated segment just before the state
    if state and state_match:
        # Get everything before the state match
        before_state = cleaned[:state_match.start()].rstrip(', ')
        # Split by comma and take the last segment as city
        segments = [s.strip() for s in before_state.split(',') if s.strip()]
        if segments:
            city = segments[-1]
    else:
        # Fallback: last comma-separated part before postcode
        parts = [p.strip() for p in cleaned.split(',')]
        if len(parts) >= 2:
            city = parts[-1].strip()

    return {"location_city": city, "location_state": state, "location_country": country}


def _extract_domain(url: str) -> str | None:
    """Extract domain from a URL."""
    if not url:
        return None
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        domain = domain.lower().removeprefix("www.")
        return domain if domain else None
    except Exception:
        return None


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

                # --- Primary: public Corrosion Control Directory ---
                try:
                    page.goto(DIRECTORY_URL, timeout=20000)
                    page.wait_for_load_state("domcontentloaded", timeout=15000)

                    # Wait for DataTable to initialise
                    page.wait_for_selector("table tbody tr", timeout=15000)

                    # Show 100 entries to minimise pagination
                    try:
                        page.select_option(
                            'select[name$="_length"]',  # DataTables length select
                            value="100",
                        )
                        # Wait for table to re-render after changing page size
                        page.wait_for_timeout(2000)
                        page.wait_for_selector("table tbody tr", timeout=10000)
                    except Exception as e:
                        logger.warning(f"[ACA] Could not change page size: {e}")

                    results = self._extract_directory_rows(page)
                    logger.info(f"[ACA] Directory: found {len(results)} entries")

                except Exception as e:
                    logger.warning(f"[ACA] Failed to scrape directory: {e}")

                # --- Fallback: auth-based member directory ---
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

        if not results:
            logger.info("[ACA] No live results — falling back to demo data")
            return self.generate_demo_results(config)

        return results[:max_results]

    def _extract_directory_rows(self, page) -> list[ScraperResult]:
        """Extract leads from the Corrosion Control Directory DataTable."""
        results: list[ScraperResult] = []
        rows = page.query_selector_all("table tbody tr")

        for row in rows:
            try:
                cells = row.query_selector_all("td")
                if len(cells) < 3:
                    continue

                # --- Column 1: Company ---
                company_cell = cells[0]
                strong_el = company_cell.query_selector("strong")
                company_name = strong_el.inner_text().strip() if strong_el else None
                if not company_name:
                    continue

                # Website link
                website_link = company_cell.query_selector('a[href*="://"]')
                website_url = None
                if website_link:
                    href = website_link.get_attribute("href") or ""
                    # Skip tel: and mailto: links
                    if href.startswith("http"):
                        website_url = href
                company_domain = _extract_domain(website_url)

                # --- Column 3: Contact ---
                contact_cell = cells[2]
                p_tags = contact_cell.query_selector_all("p")

                contact_name = ""
                phone = None
                address_parts = []

                for i, p_tag in enumerate(p_tags):
                    text = p_tag.inner_text().strip()
                    if not text:
                        continue

                    # First non-empty <p> is the contact name
                    if i == 0:
                        contact_name = text
                        continue

                    # Check for phone link
                    phone_link = p_tag.query_selector('a[href^="tel:"]')
                    if phone_link:
                        phone = phone_link.inner_text().strip()
                        continue

                    # Remaining are address lines
                    address_parts.append(text)

                if not contact_name:
                    # Fallback: try raw text
                    raw = contact_cell.inner_text().strip()
                    lines = [l.strip() for l in raw.split("\n") if l.strip()]
                    if lines:
                        contact_name = lines[0]

                first_name, last_name = _parse_name(contact_name)
                if not first_name:
                    continue

                address_text = ", ".join(address_parts)
                location = _parse_address(address_text) if address_text else {
                    "location_city": None,
                    "location_state": None,
                    "location_country": "AU",
                }

                results.append({
                    "first_name": first_name,
                    "last_name": last_name,
                    "job_title": None,
                    "company_name": company_name,
                    "company_domain": company_domain,
                    "linkedin_url": None,
                    "location_city": location["location_city"],
                    "location_state": location["location_state"],
                    "location_country": location["location_country"],
                    "source_url": DIRECTORY_URL,
                    "source_name": "ACA",
                })

            except Exception as e:
                logger.debug(f"[ACA] Skipping row: {e}")
                continue

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
            results = self._extract_directory_rows(page)
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
