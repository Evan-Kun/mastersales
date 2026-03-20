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
                browser = p.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                page = browser.new_page(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                )

                # Always scrape AusTender (federal)
                portals_to_scrape = ["austender"]
                # Only add state portals if explicitly selected (not by default — too slow)
                if states:
                    for slug, portal in AU_PORTALS.items():
                        if slug == "austender":
                            continue
                        if portal.get("state") in states:
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
        """Scrape AusTender Contract Notices via the 'View by Publish Date' button.

        Navigates to /cn/search, clicks the 'View' button to load results
        at /Cn/List?Weekly=..., then extracts data from <article> elements.
        Paginates via ?Weekly=...&page=N links until limit is reached.
        """
        results: list[ScraperResult] = []
        base_url = portal["base_url"]
        url = f"{base_url}{portal['search_path']}"

        try:
            page.goto(url, timeout=25000)
            page.wait_for_load_state("domcontentloaded", timeout=15000)

            # Click the "View" button to load results by publish date
            try:
                page.get_by_role("button", name="View").click()
            except Exception:
                try:
                    page.locator('button:has-text("View")').click()
                except Exception:
                    # Last resort: submit the form
                    page.get_by_role("button", name="Search").click()

            page.wait_for_load_state("domcontentloaded", timeout=20000)

            # Extract results from articles, paginating as needed
            while len(results) < limit:
                page_results = self._extract_article_results(page, portal)
                if not page_results:
                    break
                results.extend(page_results)

                if len(results) >= limit:
                    break

                # Try to navigate to the next page
                next_link = page.query_selector('a[href*="page="]')
                # Find the "next page" link — look for page=N where N > current
                next_page_found = False
                links = page.query_selector_all('a[href*="page="]')
                for link in links:
                    text = link.inner_text().strip()
                    # Look for "Next" or ">" or a number that's the next page
                    if text in ("Next", ">", "»", "next"):
                        link.click()
                        page.wait_for_load_state("domcontentloaded", timeout=15000)
                        next_page_found = True
                        break
                if not next_page_found:
                    break

        except Exception as e:
            logger.warning(f"[AU Tenders] AusTender CN scrape error: {e}")

        return results[:limit]

    def _extract_article_results(self, page, portal: dict) -> list[ScraperResult]:
        """Extract company/contact data from AusTender <article> elements.

        Each article contains a heading (contract title) and div pairs
        with labels like 'Supplier Name:', 'Agency:', 'Contract Value (AUD):'.
        """
        results = []
        base_url = portal["base_url"]
        articles = page.query_selector_all("article")

        for article in articles:
            try:
                text = article.inner_text()
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                if len(lines) < 2:
                    continue

                # Extract fields by looking for label patterns in the text
                supplier_name = None
                agency = None
                contract_value = None
                title = None

                # Try to get heading (h2) for contract title
                heading = article.query_selector("h2, h3, heading")
                if heading:
                    title = heading.inner_text().strip()
                elif lines:
                    title = lines[0]

                # Parse label-value pairs from text lines
                for i, line in enumerate(lines):
                    lower = line.lower()
                    if "supplier name" in lower and ":" in line:
                        # Value is either after the colon or on the next line
                        after_colon = line.split(":", 1)[-1].strip()
                        if after_colon:
                            supplier_name = after_colon
                        elif i + 1 < len(lines):
                            supplier_name = lines[i + 1]
                    elif "agency" in lower and ":" in line:
                        after_colon = line.split(":", 1)[-1].strip()
                        if after_colon:
                            agency = after_colon
                        elif i + 1 < len(lines):
                            agency = lines[i + 1]
                    elif "contract value" in lower and ":" in line:
                        after_colon = line.split(":", 1)[-1].strip()
                        if after_colon:
                            contract_value = after_colon
                        elif i + 1 < len(lines):
                            contract_value = lines[i + 1]

                company_name = supplier_name or agency or title or "Unknown"

                # Try to find "Full Details" link for source URL
                source_url = None
                links = article.query_selector_all("a[href]")
                for link in links:
                    link_text = link.inner_text().strip().lower()
                    if "full details" in link_text or "detail" in link_text:
                        href = link.get_attribute("href")
                        if href:
                            source_url = href if href.startswith("http") else f"{base_url}{href}"
                        break
                # Fallback: use first link
                if not source_url and links:
                    href = links[0].get_attribute("href")
                    if href:
                        source_url = href if href.startswith("http") else f"{base_url}{href}"

                results.append({
                    "first_name": "Unknown",
                    "last_name": "Contact",
                    "job_title": "Contract Officer",
                    "company_name": company_name,
                    "company_domain": None,
                    "linkedin_url": None,
                    "location_city": None,
                    "location_state": portal.get("state"),
                    "location_country": "AU",
                    "source_url": source_url or f"{base_url}{portal['search_path']}",
                    "source_name": portal["name"],
                })
            except Exception:
                continue

        return results

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
        """Extract company/contact data from tender search results.

        Handles both <article>-based layouts (AusTender) and traditional
        table/list layouts (state portals).
        """
        # First try article-based extraction (AusTender style)
        articles = page.query_selector_all("article")
        if articles:
            return self._extract_article_results(page, portal)

        # Fallback: table rows or list items (state portals)
        results = []
        row_selectors = [
            "table tbody tr", ".search-result", ".tender-item",
            ".result-item", ".list-group-item",
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

                company_name = None
                contact_name = None

                for line in lines:
                    lower = line.lower()
                    # Look for supplier/company name patterns
                    if "supplier name" in lower and ":" in line:
                        company_name = line.split(":", 1)[-1].strip()
                    elif any(kw in lower for kw in ("pty ltd", "group", "services", "engineering", "steel")):
                        company_name = line.strip()
                    if "contact" in lower and ":" in line:
                        contact_name = line.split(":")[-1].strip()

                if not company_name:
                    company_name = lines[1] if len(lines) > 1 else "Unknown"

                first_name = "Unknown"
                last_name = "Contact"
                if contact_name:
                    parts = contact_name.split()
                    if len(parts) >= 2:
                        first_name = parts[0]
                        last_name = " ".join(parts[1:])
                    elif len(parts) == 1:
                        first_name = parts[0]

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
        """Required by ABC but never called — returns empty list."""
        return []
