import re
import time
import json
import random
import logging
import os
from urllib.parse import quote_plus
from playwright.sync_api import sync_playwright
from config import settings

logger = logging.getLogger("mastersales.scraper")

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")

# LinkedIn geoUrn IDs for location filtering
GEO_URNS = {
    "Australia": ["101452733"],
    "New Zealand": ["104107862"],
    "Western Australia, Australia": ["106164952"],
    "Victoria, Australia": ["100803684"],
    "New South Wales, Australia": ["104769905"],
    "Queensland, Australia": ["104166042"],
    # Combined
    "AU": ["101452733"],
    "NZ": ["104107862"],
    "AU+NZ": ["101452733", "104107862"],
}

def _build_geo_param(location: str) -> str:
    """Convert location string to LinkedIn geoUrn URL parameter."""
    # Check exact match first
    urns = GEO_URNS.get(location)

    if not urns:
        # Try fuzzy matching
        loc_lower = location.lower()
        if ("australia" in loc_lower and "new zealand" in loc_lower) or "au+nz" in loc_lower or "au & nz" in loc_lower:
            urns = GEO_URNS["AU+NZ"]
        elif "western australia" in loc_lower or loc_lower == "wa":
            urns = GEO_URNS["Western Australia, Australia"]
        elif "victoria" in loc_lower or loc_lower == "vic":
            urns = GEO_URNS["Victoria, Australia"]
        elif "new south wales" in loc_lower or loc_lower == "nsw":
            urns = GEO_URNS["New South Wales, Australia"]
        elif "new zealand" in loc_lower or loc_lower == "nz":
            urns = GEO_URNS["NZ"]
        elif "australia" in loc_lower or loc_lower == "au":
            urns = GEO_URNS["AU"]

    if not urns:
        # Default: Australia + New Zealand
        urns = GEO_URNS["AU+NZ"]

    # LinkedIn format: geoUrn=["id1","id2"]
    urn_list = "%5B" + "%2C".join(f"%22{u}%22" for u in urns) + "%5D"
    return f"&geoUrn={urn_list}"


class LinkedInScraper:
    """Playwright-based LinkedIn scraper using network interception."""

    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.browser = None
        self.page = None
        self._api_responses = []

    def _random_delay(self, label: str = ""):
        delay = random.uniform(settings.scrape_delay_min, settings.scrape_delay_max)
        if label:
            logger.info(f"  [{label}] waiting {delay:.1f}s...")
        time.sleep(delay)

    def _screenshot(self, name: str):
        """Save a debug screenshot."""
        try:
            path = os.path.join(OUTPUT_DIR, f"{name}.png")
            self.page.screenshot(path=path, full_page=True)
            logger.info(f"  Screenshot saved: {path}")
        except Exception as e:
            logger.warning(f"  Screenshot failed: {e}")

    def _login(self):
        """Log into LinkedIn."""
        logger.info("=" * 50)
        logger.info("SCRAPER: Starting LinkedIn login...")
        logger.info(f"  Email: {self.email[:3]}***@{self.email.split('@')[-1] if '@' in self.email else '***'}")

        self.page.goto("https://www.linkedin.com/login")
        self._random_delay("login page load")

        # LinkedIn updated their login page — try multiple selectors
        logger.info("  Filling credentials...")
        email_filled = False
        for selector in ['#username', 'input[name="session_key"]', 'input[autocomplete="username"]']:
            try:
                el = self.page.query_selector(selector)
                if el:
                    el.fill(self.email)
                    email_filled = True
                    logger.info(f"  Email filled via: {selector}")
                    break
            except Exception:
                continue

        if not email_filled:
            # LinkedIn may render duplicate inputs (desktop + mobile) — use .first
            self.page.get_by_label("Email or phone").first.fill(self.email)
            logger.info("  Email filled via label 'Email or phone' (.first)")

        pwd_filled = False
        for selector in ['#password', 'input[name="session_password"]', 'input[autocomplete="current-password"]']:
            try:
                el = self.page.query_selector(selector)
                if el:
                    el.fill(self.password)
                    pwd_filled = True
                    logger.info(f"  Password filled via: {selector}")
                    break
            except Exception:
                continue

        if not pwd_filled:
            self.page.get_by_label("Password").first.fill(self.password)
            logger.info("  Password filled via label 'Password' (.first)")

        logger.info("  Submitting login form...")
        # Try multiple submit selectors
        submitted = False
        for selector in ['button[type="submit"]', 'button:has-text("Sign in")', 'button.btn__primary--large']:
            try:
                el = self.page.query_selector(selector)
                if el:
                    el.click()
                    submitted = True
                    break
            except Exception:
                continue
        if not submitted:
            self.page.get_by_role("button", name="Sign in").first.click()
        self._random_delay("login submit")

        try:
            self.page.wait_for_url("**/feed*", timeout=30000)
            logger.info("  LOGIN SUCCESS - redirected to feed")
        except Exception as e:
            current_url = self.page.url
            # Check if we actually landed on feed despite the timeout
            if "/feed" in current_url:
                logger.info("  LOGIN SUCCESS - on feed (detected after wait)")
                return

            logger.error(f"  LOGIN FAILED - stuck at: {current_url}")

            if "checkpoint" in current_url:
                logger.error("  REASON: LinkedIn security checkpoint (CAPTCHA/verification required)")
                logger.error("  FIX: Log into LinkedIn manually in a browser first, then retry")
            elif "login" in current_url:
                logger.error("  REASON: Bad credentials or account locked")
            else:
                logger.error(f"  REASON: Unexpected redirect to {current_url}")

            self._screenshot("login_error")
            raise Exception(f"LinkedIn login failed. Current URL: {current_url}")

    def _on_response(self, response):
        """Intercept LinkedIn API responses containing search results."""
        url = response.url
        # LinkedIn API endpoints that may contain search data
        is_search_api = (
            "voyager/api" in url and ("search" in url or "typeahead" in url or "cluster" in url)
        ) or (
            "graphql" in url
        ) or (
            "voyager" in url and "people" in url
        )

        if is_search_api:
            try:
                ct = response.headers.get("content-type", "")
                if response.status == 200 and ("json" in ct or "octet-stream" in ct):
                    body = response.json()
                    self._api_responses.append(body)
                    logger.info(f"  Intercepted API: ...{url.split('?')[0][-60:]}")
            except Exception:
                pass

    def search_people(self, keywords: list[str], location: str, max_results: int = 20) -> list[dict]:
        """Search LinkedIn for people matching keywords and location.

        Uses DOM extraction as the primary strategy since it reads the rendered
        search result cards directly. API interception supplements with extra data.
        """
        results = []
        seen_urls = set()

        # Build search queries: use individual keywords or small pairs
        search_queries = self._build_search_queries(keywords)

        logger.info("=" * 50)
        logger.info("SCRAPER: Initializing Playwright browser...")
        logger.info(f"  Keywords: {keywords}")
        logger.info(f"  Search queries: {search_queries}")
        logger.info(f"  Location: {location}")
        logger.info(f"  Max results: {max_results}")

        with sync_playwright() as p:
            logger.info("  Launching headless Chromium...")
            self.browser = p.chromium.launch(headless=True)
            context = self.browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            )
            self.page = context.new_page()

            # Intercept network responses
            self.page.on("response", self._on_response)

            try:
                self._login()

                geo_param = _build_geo_param(location)
                logger.info(f"  Geo filter: {location} → {geo_param}")

                for q_idx, query in enumerate(search_queries):
                    if len(results) >= max_results:
                        break

                    search_url = f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(query)}&origin=GLOBAL_SEARCH_HEADER{geo_param}"
                    logger.info(f"SCRAPER: Search {q_idx+1}/{len(search_queries)}: \"{query}\"")
                    logger.info(f"  URL: {search_url[:100]}...")

                    page_num = 1
                    empty_pages = 0
                    while len(results) < max_results:
                        self._api_responses.clear()

                        if page_num == 1:
                            self.page.goto(search_url)
                        else:
                            self.page.goto(f"{search_url}&page={page_num}")

                        self._random_delay("search page load")
                        self.page.wait_for_load_state("domcontentloaded", timeout=15000)
                        time.sleep(3)

                        # Scroll to trigger lazy loading
                        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(2)

                        self._screenshot(f"search_q{q_idx+1}_page_{page_num}")

                        # Save HTML for first search for debugging
                        if q_idx == 0 and page_num == 1:
                            try:
                                html_path = os.path.join(OUTPUT_DIR, "search_page_debug.html")
                                with open(html_path, "w", encoding="utf-8") as f:
                                    f.write(self.page.content())
                                logger.info(f"  Page HTML saved: {html_path}")
                            except Exception:
                                pass

                        logger.info(f"  Processing page {page_num}...")

                        # DOM extraction is our primary strategy
                        page_people = self._extract_from_dom()
                        logger.info(f"  DOM extraction: found {len(page_people)} people")

                        # API interception as supplement for missing fields
                        logger.info(f"  API responses intercepted: {len(self._api_responses)}")

                        # Save raw API JSON for debugging (first search only)
                        if q_idx == 0 and page_num == 1 and self._api_responses:
                            try:
                                dump_path = os.path.join(OUTPUT_DIR, "api_response_debug.json")
                                with open(dump_path, "w") as f:
                                    json.dump(self._api_responses, f, indent=2, default=str)
                                logger.info(f"  API JSON saved: {dump_path}")
                            except Exception as e:
                                logger.warning(f"  Failed to save API JSON: {e}")

                        api_people = self._extract_from_api_responses()
                        if api_people:
                            logger.info(f"  API extraction: {len(api_people)} people")
                            # Merge API data into DOM results where fields are missing
                            self._merge_api_into_dom(page_people, api_people)

                        if not page_people:
                            logger.warning(f"  No results on page {page_num}")
                            empty_pages += 1
                            if empty_pages >= 2 or page_num == 1:
                                self._dump_page_debug()
                                break
                            continue

                        # Add new (non-duplicate) results
                        new_count = 0
                        for person in page_people:
                            if len(results) >= max_results:
                                break
                            dedup_key = person.get("linkedin_url") or f"{person['first_name']}_{person['last_name']}"
                            if dedup_key in seen_urls:
                                continue
                            seen_urls.add(dedup_key)
                            results.append(person)
                            new_count += 1
                            logger.info(f"  [{len(results)}/{max_results}] {person['first_name']} {person['last_name']} - {person.get('job_title', '')[:50]}")

                        logger.info(f"  Page {page_num}: {len(page_people)} found, {new_count} new (total: {len(results)})")

                        if len(results) >= max_results:
                            break

                        # Check for next page
                        has_next = self.page.evaluate('''
                            () => {
                                const btns = document.querySelectorAll('button[aria-label="Next"]');
                                for (const btn of btns) {
                                    if (!btn.disabled) return true;
                                }
                                return false;
                            }
                        ''')
                        if not has_next:
                            logger.info(f"  No more pages for \"{query}\"")
                            break

                        logger.info(f"  Moving to page {page_num + 1}...")
                        page_num += 1
                        self._random_delay("next page")

                    self._random_delay("between searches")

            except Exception as e:
                logger.error(f"SCRAPER ERROR: {e}")
                self._screenshot("scraper_error")
                raise
            finally:
                logger.info("SCRAPER: Closing browser...")
                self.browser.close()

        logger.info("=" * 50)
        logger.info(f"SCRAPER: Complete. Found {len(results)} leads.")
        logger.info("=" * 50)
        return results

    def _build_search_queries(self, keywords: list[str]) -> list[str]:
        """Build effective LinkedIn search queries from a keyword list.

        LinkedIn returns very few results when too many keywords are combined,
        so we split into focused queries of 1-2 keywords each.
        """
        if len(keywords) <= 2:
            return [" ".join(keywords)]

        queries = []
        # First: each keyword individually (best coverage)
        for kw in keywords:
            queries.append(kw)

        # Then: strategic pairs for more specific results
        if len(keywords) >= 4:
            pairs = [
                (keywords[0], keywords[1]),
                (keywords[0], keywords[2]),
                (keywords[1], keywords[3]) if len(keywords) > 3 else (keywords[1], keywords[2]),
            ]
            for a, b in pairs:
                q = f"{a} {b}"
                if q not in queries:
                    queries.append(q)

        return queries

    # ── DOM extraction (primary) ─────────────────────────────────────────

    def _extract_from_dom(self) -> list[dict]:
        """Extract people from DOM using LinkedIn's current HTML structure.

        LinkedIn uses data-view-name="people-search-result" cards with:
        - a[data-view-name="search-result-lockup-title"] for the name
        - Sequential <p> tags for headline and location
        - Outer <a href="/in/..."> for the profile URL
        """
        people = []

        raw = self.page.evaluate('''
            () => {
                const results = [];
                const cards = document.querySelectorAll('[data-view-name="people-search-result"]');

                for (const card of cards) {
                    // Get profile URL from the card's <a> with /in/ href
                    let url = '';
                    const profileLink = card.querySelector('a[href*="/in/"]');
                    if (profileLink) {
                        url = profileLink.href.split('?')[0];
                    }

                    // Get name from the search-result-lockup-title link
                    let name = '';
                    const nameEl = card.querySelector('a[data-view-name="search-result-lockup-title"]');
                    if (nameEl) {
                        name = nameEl.textContent.trim();
                    }

                    // Get headline and location from <p> tags
                    // The card structure has: name <p>, then headline <p>, then location <p>
                    const allPs = card.querySelectorAll('p');
                    const textLines = [];
                    for (const p of allPs) {
                        const text = p.textContent.trim();
                        if (!text || text.length < 2) continue;
                        // Skip if this <p> contains the name
                        if (name && text.includes(name)) continue;
                        // Skip connection degree markers
                        if (/^[•·]?\s*(1st|2nd|3rd)\+?$/.test(text)) continue;
                        textLines.push(text);
                    }

                    // Also check for "Current:/Past:" info in the full card text
                    const fullText = card.innerText || '';

                    results.push({
                        name: name,
                        url: url,
                        lines: textLines.slice(0, 6),
                        fullText: fullText
                    });
                }
                return results;
            }
        ''')

        for item in raw:
            person = self._parse_dom_card(item)
            if person:
                people.append(person)

        return people

    def _parse_dom_card(self, item: dict) -> dict | None:
        """Parse a DOM-extracted card into structured person data."""
        full_name = item.get("name", "").strip()
        url = item.get("url", "")
        lines = item.get("lines", [])
        full_text = item.get("fullText", "")

        # Clean the name — remove connection degree suffixes
        full_name = re.sub(r'\s*[•·]\s*(1st|2nd|3rd)\+?\s*$', '', full_name).strip()

        if not full_name or full_name == "LinkedIn Member" or len(full_name) < 2:
            return None

        parts = full_name.split(" ", 1)
        first_name = parts[0] if parts else ""
        last_name = parts[1] if len(parts) > 1 else ""

        # Parse structured paragraph lines
        # Typical order: [headline/job title], [location], ...
        job_title = ""
        location_text = ""
        company_name = ""

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Skip noise
            if line in ("Connect", "Message", "Follow", "Pending", "View",
                        "View profile", "Send InMail", "More", "…", "Promoted"):
                continue
            if line.startswith("Are these results") or line.startswith("Try Premium"):
                continue

            # Location: contains Australian/NZ state or country names
            if not location_text and re.search(
                r'(Australia|New Zealand|Victoria|Queensland|Western Australia|'
                r'New South Wales|South Australia|Tasmania|Northern Territory|'
                r'NSW|WA|VIC|QLD|SA|TAS|NT|ACT|'
                r'Auckland|Wellington|Canterbury|Waikato|Greater .+ Area)',
                line
            ):
                location_text = line
                continue

            # "Current:" or "Past:" lines for company info
            if line.startswith("Current:") or line.startswith("Past:"):
                if " at " in line:
                    at_parts = line.split(" at ", 1)
                    company_name = at_parts[1].strip()
                    company_name = re.sub(r'\s*\(.*?\)\s*$', '', company_name).strip()
                continue

            # First non-location, non-noise line is the headline/job title
            if not job_title and len(line) > 2:
                job_title = line
                continue

        # Split "Title at Company" from headline
        if " at " in job_title and not company_name:
            t_parts = job_title.split(" at ", 1)
            job_title = t_parts[0].strip()
            company_name = t_parts[1].strip()

        # Also try "Title @ Company" pattern
        if " @ " in job_title and not company_name:
            t_parts = job_title.split(" @ ", 1)
            job_title = t_parts[0].strip()
            company_name = t_parts[1].strip()

        # If no company from headline, try fullText for "Current:" lines
        if not company_name and full_text:
            current_match = re.search(r'Current:\s*(.+?)(?:\n|$)', full_text)
            if current_match:
                current_line = current_match.group(1).strip()
                if " at " in current_line:
                    company_name = current_line.split(" at ", 1)[1].strip()
                    company_name = re.sub(r'\s*\(.*?\)\s*$', '', company_name).strip()

        # Parse location into city/state/country
        location_city = ""
        location_state = ""
        location_country = "AU"
        if location_text:
            # Handle "Greater X Area" format
            location_text = re.sub(r'^Greater\s+', '', location_text)
            location_text = re.sub(r'\s+Area$', '', location_text)

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
            "company_name": company_name,
            "linkedin_url": url,
            "location_city": location_city,
            "location_state": location_state,
            "location_country": location_country,
        }

    # ── API extraction (supplementary) ───────────────────────────────────

    def _extract_from_api_responses(self) -> list[dict]:
        """Parse people from intercepted LinkedIn API JSON responses."""
        people = []

        for response_body in self._api_responses:
            try:
                self._walk_json_for_people(response_body, people)
            except Exception as e:
                logger.debug(f"  API parse error: {e}")

        # Dedupe by linkedin_url
        seen = set()
        unique = []
        for p in people:
            key = p.get("linkedin_url") or f"{p['first_name']}_{p['last_name']}"
            if key not in seen:
                seen.add(key)
                unique.append(p)

        return unique

    def _walk_json_for_people(self, obj, people: list, depth: int = 0):
        """Recursively walk JSON to find person data structures."""
        if depth > 15:
            return

        if isinstance(obj, dict):
            if self._is_person_dict(obj):
                person = self._parse_person_dict(obj)
                if person:
                    people.append(person)
                return

            for v in obj.values():
                self._walk_json_for_people(v, people, depth + 1)

        elif isinstance(obj, list):
            for item in obj:
                self._walk_json_for_people(item, people, depth + 1)

    def _is_person_dict(self, d: dict) -> bool:
        """Check if a dict looks like a LinkedIn person result.

        Strict checks to avoid matching schema definitions like {"type": "string"}
        that happen to have keys like "title" or "firstName".
        """
        # Skip schema/metadata objects
        dtype = d.get("$type", "")
        if dtype and ("schema" in dtype.lower() or "metadata" in dtype.lower()):
            return False

        # Pattern 1: Has firstName + lastName as actual strings
        if "firstName" in d and "lastName" in d:
            fn = d["firstName"]
            ln = d["lastName"]
            # Must be real strings, not schema dicts like {"type": "string"}
            if isinstance(fn, str) and isinstance(ln, str) and fn and ln:
                has_urn = any(k in d for k in ("entityUrn", "publicIdentifier"))
                if has_urn:
                    return True

        # Pattern 2: Search result card with title + primarySubtitle
        if "title" in d and "primarySubtitle" in d:
            title = d["title"]
            # title must be a dict with "text" key, or a non-empty string
            if isinstance(title, dict) and "text" in title:
                return True
            if isinstance(title, str) and len(title) > 1 and title != "LinkedIn Member":
                return True

        # Pattern 3: Has navigationContext with /in/ URL and a real title
        nav = d.get("navigationContext") or d.get("navigationUrl", "")
        if isinstance(nav, dict):
            nav = nav.get("url", "")
        if "/in/" in str(nav):
            title = d.get("title")
            if isinstance(title, dict) and "text" in title:
                return True
            if isinstance(title, str) and len(title) > 2:
                return True

        return False

    def _parse_person_dict(self, d: dict) -> dict | None:
        """Extract structured person data from a LinkedIn API dict."""
        first_name = ""
        last_name = ""
        job_title = ""
        company_name = ""
        linkedin_url = ""
        location_text = ""

        # --- Name ---
        if "firstName" in d and "lastName" in d:
            fn = d["firstName"]
            ln = d["lastName"]
            if isinstance(fn, str) and isinstance(ln, str):
                first_name = fn
                last_name = ln
        if not first_name and "title" in d:
            title_obj = d["title"]
            if isinstance(title_obj, dict):
                full_name = title_obj.get("text", "")
            elif isinstance(title_obj, str):
                full_name = title_obj
            else:
                full_name = ""
            if full_name and full_name != "LinkedIn Member":
                parts = full_name.strip().split(" ", 1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else ""

        if not first_name:
            return None
        if first_name == "LinkedIn" and last_name == "Member":
            return None

        # --- Job Title ---
        if "primarySubtitle" in d:
            st = d["primarySubtitle"]
            job_title = st.get("text", "") if isinstance(st, dict) else str(st)
        elif "headline" in d:
            headline = d["headline"]
            if isinstance(headline, str):
                job_title = headline
            elif isinstance(headline, dict) and "text" in headline:
                job_title = headline["text"]
        elif "occupation" in d:
            job_title = str(d["occupation"])

        # Split "Title at Company" pattern
        if " at " in job_title:
            parts = job_title.split(" at ", 1)
            job_title = parts[0].strip()
            company_name = parts[1].strip()

        # --- Location ---
        if "secondarySubtitle" in d:
            st = d["secondarySubtitle"]
            location_text = st.get("text", "") if isinstance(st, dict) else str(st)
        elif "location" in d:
            loc = d["location"]
            if isinstance(loc, dict):
                location_text = loc.get("name", "") or loc.get("text", "")
            elif isinstance(loc, str):
                location_text = loc

        # --- LinkedIn URL ---
        nav = d.get("navigationContext")
        if isinstance(nav, dict):
            linkedin_url = nav.get("url", "")
        if not linkedin_url:
            linkedin_url = d.get("navigationUrl", "")
        if not linkedin_url:
            pub_id = d.get("publicIdentifier", "")
            if pub_id:
                linkedin_url = f"https://www.linkedin.com/in/{pub_id}"
        if not linkedin_url:
            urn = d.get("entityUrn", "")
            if "member" in str(urn).lower() or "profile" in str(urn).lower():
                parts = str(urn).split(":")
                if parts:
                    linkedin_url = f"https://www.linkedin.com/in/{parts[-1]}"

        # Clean URL
        if linkedin_url and "?" in linkedin_url:
            linkedin_url = linkedin_url.split("?")[0]

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
            "company_name": company_name,
            "linkedin_url": linkedin_url,
            "location_city": location_city,
            "location_state": location_state,
            "location_country": location_country,
        }

    # ── Merge API data into DOM results ──────────────────────────────────

    def _merge_api_into_dom(self, dom_people: list[dict], api_people: list[dict]):
        """Fill in missing DOM fields using API-extracted data."""
        api_by_url = {}
        api_by_name = {}
        for ap in api_people:
            if ap.get("linkedin_url"):
                api_by_url[ap["linkedin_url"]] = ap
            name_key = f"{ap['first_name']}_{ap['last_name']}".lower()
            api_by_name[name_key] = ap

        for dp in dom_people:
            # Try matching by URL first, then by name
            match = None
            if dp.get("linkedin_url"):
                match = api_by_url.get(dp["linkedin_url"])
            if not match:
                name_key = f"{dp['first_name']}_{dp['last_name']}".lower()
                match = api_by_name.get(name_key)

            if match:
                if not dp.get("job_title") and match.get("job_title"):
                    dp["job_title"] = match["job_title"]
                if not dp.get("company_name") and match.get("company_name"):
                    dp["company_name"] = match["company_name"]
                if not dp.get("location_city") and match.get("location_city"):
                    dp["location_city"] = match["location_city"]
                    dp["location_state"] = match.get("location_state", "")
                    dp["location_country"] = match.get("location_country", "AU")

    # ── Debug ────────────────────────────────────────────────────────────

    def _dump_page_debug(self):
        """Log debug info when extraction fails."""
        try:
            logger.info(f"  Page URL: {self.page.url}")
            logger.info(f"  Page title: {self.page.title()}")

            info = self.page.evaluate('''
                () => {
                    return {
                        searchCards: document.querySelectorAll('[data-view-name="people-search-result"]').length,
                        profileLinks: document.querySelectorAll('a[href*="/in/"]').length,
                        titleLinks: document.querySelectorAll('a[data-view-name="search-result-lockup-title"]').length,
                        listItems: document.querySelectorAll('[role="listitem"]').length,
                    };
                }
            ''')
            logger.info(f"  Search result cards: {info['searchCards']}")
            logger.info(f"  Profile links (/in/): {info['profileLinks']}")
            logger.info(f"  Title links: {info['titleLinks']}")
            logger.info(f"  Role=listitem elements: {info['listItems']}")

            # Save page HTML for offline debugging
            html_path = os.path.join(OUTPUT_DIR, "search_page_debug.html")
            html = self.page.content()
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)
            logger.info(f"  Full page HTML saved: {html_path}")
        except Exception as e:
            logger.warning(f"  Debug dump failed: {e}")
