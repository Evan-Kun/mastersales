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
    GETS_AWARDED = "/ExternalAwardedTenderList.htm"
    GETS_CURRENT = "/ExternalIndex.htm"

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

                # --- Phase 1: Completed/awarded tenders (supplier data) ---
                results.extend(self._scrape_gets_page(
                    page, self.GETS_AWARDED, keyword_str,
                    max_results, is_cancelled, source_label="awarded",
                ))

                # --- Phase 2: Current tenders (procuring agencies) ---
                if len(results) < max_results and not is_cancelled():
                    results.extend(self._scrape_gets_page(
                        page, self.GETS_CURRENT, keyword_str,
                        max_results - len(results), is_cancelled,
                        source_label="current",
                    ))

                browser.close()
        except Exception as e:
            logger.error(f"[GETS] Scraper error: {e}")

        return results[:max_results]

    def _scrape_gets_page(
        self, page, path: str, keyword_str: str, limit: int, is_cancelled, source_label: str
    ) -> list[ScraperResult]:
        """Scrape a single GETS listing page (awarded or current tenders)."""
        results: list[ScraperResult] = []
        url = f"{self.GETS_BASE}{path}"

        try:
            page.goto(url, timeout=20000)
            page.wait_for_load_state("domcontentloaded", timeout=15000)

            # Fill search box if keywords provided.  The GETS search form
            # uses a plain textbox without a distinguishing name attribute,
            # so we try the role-based selector first, then common fallbacks.
            if keyword_str.strip():
                filled = False
                search_selectors = [
                    'input[type="text"]',
                    'input[name="keyword"]', 'input[name="search"]',
                    'input[name="q"]', 'input[type="search"]', '#keyword',
                ]
                for sel in search_selectors:
                    try:
                        el = page.query_selector(sel)
                        if el:
                            el.fill(keyword_str)
                            filled = True
                            break
                    except Exception:
                        continue

                # If CSS selectors failed, try Playwright role locator
                if not filled:
                    try:
                        page.get_by_role("textbox").first.fill(keyword_str)
                        filled = True
                    except Exception:
                        pass

                if filled:
                    # Click the Submit button
                    submitted = False
                    for sel in [
                        'button:has-text("Submit")',
                        'input[type="submit"]',
                        'button[type="submit"]',
                    ]:
                        try:
                            btn = page.query_selector(sel)
                            if btn:
                                btn.click()
                                page.wait_for_load_state("domcontentloaded", timeout=15000)
                                submitted = True
                                break
                        except Exception:
                            continue
                    if not submitted:
                        try:
                            page.get_by_role("button", name="Submit").click()
                            page.wait_for_load_state("domcontentloaded", timeout=15000)
                        except Exception:
                            pass

            # Extract from table rows.
            # GETS tables have 6 columns:
            #   0: RFx ID, 1: Reference #, 2: Title, 3: Tender Type,
            #   4: Close Date, 5: Organisation
            rows = page.query_selector_all("table tr")
            for row in rows:
                if is_cancelled() or len(results) >= limit:
                    break

                cells = row.query_selector_all("td")
                if len(cells) < 3:
                    continue  # skip header rows or malformed rows

                # Extract title from cell index 2 (third column)
                title = ""
                if len(cells) > 2:
                    title = cells[2].inner_text().strip()

                # Extract organisation from cell index 5 (sixth column)
                organisation = ""
                if len(cells) > 5:
                    organisation = cells[5].inner_text().strip()

                company_name = organisation or title or "Unknown"

                # Try to get the detail link from the row
                link = row.query_selector("a[href]")
                source_url = url
                detail_href = None
                if link:
                    href = link.get_attribute("href")
                    if href:
                        source_url = href if href.startswith("http") else f"{self.GETS_BASE}{href}"
                        detail_href = source_url

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
                    "source_url": source_url,
                    "source_name": "GETS",
                })

            # Try to visit detail pages of awarded tenders to find supplier names
            if source_label == "awarded" and results:
                self._enrich_with_supplier_details(page, results)

        except Exception as e:
            logger.warning(f"[GETS] Error scraping {source_label} tenders: {e}")

        return results

    def _enrich_with_supplier_details(
        self, page, results: list[ScraperResult], max_detail_visits: int = 5
    ) -> None:
        """Visit individual tender detail pages to extract supplier names."""
        visited = 0
        for result in results:
            if visited >= max_detail_visits:
                break
            detail_url = result.get("source_url", "")
            if not detail_url or detail_url == f"{self.GETS_BASE}{self.GETS_AWARDED}":
                continue
            try:
                page.goto(detail_url, timeout=15000)
                page.wait_for_load_state("domcontentloaded", timeout=10000)
                visited += 1

                # Look for supplier/awardee info on the detail page
                body_text = page.inner_text("body")
                for marker in ("Supplier:", "Awarded to:", "Successful Tenderer:",
                               "Awardee:", "Contractor:"):
                    if marker.lower() in body_text.lower():
                        idx = body_text.lower().index(marker.lower())
                        snippet = body_text[idx + len(marker):idx + len(marker) + 200]
                        supplier_name = snippet.split("\n")[0].strip()
                        if supplier_name:
                            result["company_name"] = supplier_name
                            break
            except Exception:
                continue

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
