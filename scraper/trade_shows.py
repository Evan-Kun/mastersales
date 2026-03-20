# scraper/trade_shows.py
import logging
from scraper.base import BaseScraper, ScraperConfig, ScraperResult

logger = logging.getLogger("mastersales.scraper.trade_shows")

HARDCODED_EVENTS = {
    "imarc": {
        "name": "IMARC Mining Conference",
        "urls": [
            "https://imarcglobal.com/exhibitors",
        ],
    },
    "aca_conf": {
        "name": "ACA Corrosion & Prevention",
        "urls": [
            "https://corrosion-prevention2026.eventsair.site/exhibitors",
        ],
    },
    "austmine": {
        "name": "Austmine / GRX",
        "urls": [
            "https://www.grx.au/",
        ],
    },
    "ampp_annual": {
        "name": "AMPP Annual Conference",
        "urls": [
            "https://ace.ampp.org/exhibitors",
        ],
    },
    "aimex": {
        "name": "AIMEX Mining Exhibition",
        "urls": [
            "https://www.aimex.com.au/",
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
            logger.warning("[Trade Shows] Playwright not installed — cannot scrape")
            return []

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
        """Required by ABC but never called — returns empty list."""
        return []
