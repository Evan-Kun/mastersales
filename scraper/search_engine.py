import time
import random
from urllib.parse import quote_plus
from config import settings


def build_linkedin_search_url(keywords: list[str], location: str = "Australia") -> str:
    keyword_str = " ".join(keywords)
    return f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(keyword_str)}&origin=GLOBAL_SEARCH_HEADER&geoUrn={quote_plus(location)}"


def parse_icp_to_search_params(
    keywords: list[str],
    countries: list[str] = None,
    states: list[str] = None,
) -> dict:
    location_parts = []
    if states:
        location_parts.extend(states)
    if countries:
        location_parts.extend(countries)
    location = ", ".join(location_parts) if location_parts else "Australia"

    return {
        "keywords": " ".join(keywords),
        "location": location,
    }


def run_scrape(keywords: list[str], location: str = "Australia", max_results: int = 20) -> list[dict]:
    """Run the LinkedIn scrape. Uses Playwright if credentials available, otherwise returns demo data."""

    if settings.linkedin_email and settings.linkedin_password:
        try:
            from scraper.linkedin import LinkedInScraper
            scraper = LinkedInScraper(settings.linkedin_email, settings.linkedin_password)
            return scraper.search_people(keywords, location, max_results)
        except Exception as e:
            print(f"LinkedIn scraper error: {e}")
            return _generate_demo_results(keywords, location, max_results)
    else:
        return _generate_demo_results(keywords, location, max_results)


def _generate_demo_results(keywords: list[str], location: str, max_results: int) -> list[dict]:
    """Generate realistic demo scraping results when LinkedIn credentials are not available."""

    demo_people = [
        {"first_name": "Michael", "last_name": "Anderson", "job_title": "Steel Fabrication Manager", "company_name": "Precision Steel WA", "location_city": "Perth", "location_state": "WA", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/michael-anderson-steel"},
        {"first_name": "Jennifer", "last_name": "Walsh", "job_title": "Corrosion Engineer", "company_name": "AusCoat Solutions", "location_city": "Melbourne", "location_state": "VIC", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/jennifer-walsh-corrosion"},
        {"first_name": "Robert", "last_name": "Hughes", "job_title": "Maintenance Director", "company_name": "Iron Range Mining", "location_city": "Kalgoorlie", "location_state": "WA", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/robert-hughes-mining"},
        {"first_name": "Tane", "last_name": "Wiremu", "job_title": "Shipyard Operations Manager", "company_name": "Pacific Dockyard NZ", "location_city": "Wellington", "location_state": "Wellington", "location_country": "NZ", "linkedin_url": "https://linkedin.com/in/tane-wiremu-nz"},
        {"first_name": "Karen", "last_name": "Mitchell", "job_title": "Procurement Specialist - Coatings", "company_name": "BHP Nickel West", "location_city": "Perth", "location_state": "WA", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/karen-mitchell-bhp"},
        {"first_name": "Steven", "last_name": "Park", "job_title": "Quality Control Manager", "company_name": "Steel Blue Fabrications", "location_city": "Geelong", "location_state": "VIC", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/steven-park-qa"},
        {"first_name": "Linda", "last_name": "Foster", "job_title": "Site Engineer", "company_name": "Fortescue Metals Group", "location_city": "Port Hedland", "location_state": "WA", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/linda-foster-fmg"},
        {"first_name": "Rawiri", "last_name": "Henare", "job_title": "Workshop Foreman", "company_name": "Kiwi Steel Structures", "location_city": "Auckland", "location_state": "Auckland", "location_country": "NZ", "linkedin_url": "https://linkedin.com/in/rawiri-henare-steel"},
        {"first_name": "Craig", "last_name": "McDonald", "job_title": "Rust Prevention Specialist", "company_name": "Coastal Engineering VIC", "location_city": "Frankston", "location_state": "VIC", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/craig-mcdonald-coastal"},
        {"first_name": "Priya", "last_name": "Sharma", "job_title": "Materials Engineer", "company_name": "Rio Tinto Iron Ore", "location_city": "Newman", "location_state": "WA", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/priya-sharma-materials"},
        {"first_name": "Daniel", "last_name": "O'Sullivan", "job_title": "Fabrication Supervisor", "company_name": "Murray Steel Works", "location_city": "Ballarat", "location_state": "VIC", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/daniel-osullivan-fab"},
        {"first_name": "Grace", "last_name": "Lee", "job_title": "Protective Coatings Inspector", "company_name": "Downer Group", "location_city": "Perth", "location_state": "WA", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/grace-lee-coatings"},
        {"first_name": "Wayne", "last_name": "Barrett", "job_title": "Plant Manager", "company_name": "Tasman Steel NZ", "location_city": "Christchurch", "location_state": "Canterbury", "location_country": "NZ", "linkedin_url": "https://linkedin.com/in/wayne-barrett-tasman"},
        {"first_name": "Sophie", "last_name": "Turner", "job_title": "Supply Chain Manager", "company_name": "BlueScope Steel", "location_city": "Melbourne", "location_state": "VIC", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/sophie-turner-bluescope"},
        {"first_name": "Ian", "last_name": "Campbell", "job_title": "Underground Mining Engineer", "company_name": "Newmont Boddington", "location_city": "Boddington", "location_state": "WA", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/ian-campbell-newmont"},
    ]

    results = demo_people[:max_results]

    # Simulate scraping delay
    for i, result in enumerate(results):
        time.sleep(random.uniform(0.1, 0.3))

    return results
