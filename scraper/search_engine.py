import time
import random
import logging
from urllib.parse import quote_plus
from config import settings

logger = logging.getLogger("mastersales.scraper")


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


def run_scrape(
    keywords: list[str],
    location: str = "Australia",
    max_results: int = 20,
    linkedin_email: str = "",
    linkedin_password: str = "",
) -> list[dict]:
    """Run the LinkedIn scrape. Uses Playwright if credentials available, otherwise returns demo data.

    Args:
        linkedin_email: Override credentials (from web UI). Falls back to global .env config.
        linkedin_password: Override credentials (from web UI). Falls back to global .env config.
    """
    # Use provided credentials, fall back to global config
    email = linkedin_email or settings.linkedin_email
    password = linkedin_password or settings.linkedin_password

    logger.info("=" * 50)
    logger.info("SCRAPE JOB STARTED")
    logger.info(f"  Keywords: {keywords}")
    logger.info(f"  Location: {location}")
    logger.info(f"  Max results: {max_results}")
    logger.info(f"  LinkedIn credentials: {'configured' if email else 'NOT SET (demo mode)'}")
    logger.info(f"  Credential source: {'web UI' if linkedin_email else '.env config' if email else 'none'}")
    logger.info("=" * 50)

    if email and password:
        logger.info("MODE: Live LinkedIn scraping")
        from scraper.linkedin import LinkedInScraper
        scraper = LinkedInScraper(email, password)
        results = scraper.search_people(keywords, location, max_results)
        logger.info(f"SCRAPE JOB COMPLETE: {len(results)} leads found via LinkedIn")
        return results
    else:
        logger.info("MODE: Demo data (no LinkedIn credentials)")
        return _generate_demo_results(keywords, location, max_results)


_FIRST_NAMES = [
    "Michael", "Jennifer", "Robert", "Tane", "Karen", "Steven", "Linda", "Rawiri",
    "Craig", "Priya", "Daniel", "Grace", "Wayne", "Sophie", "Ian", "David",
    "Sarah", "James", "Emily", "Mark", "Aroha", "Peter", "Megan", "Hemi",
    "Andrew", "Rachel", "Scott", "Nikita", "Tom", "Anita", "Brett", "Claire",
    "Nathan", "Lisa", "Aaron", "Deepa", "Paul", "Joanne", "Ravi", "Bridget",
    "Shane", "Kylie", "Liam", "Fatima", "Chris", "Ngaire", "Adam", "Wendy",
    "George", "Tamara", "Marcus", "Ingrid", "Wiremu", "Katrina", "Darren", "Mei",
    "Colin", "Vanessa", "Ethan", "Sonia",
]

_LAST_NAMES = [
    "Anderson", "Walsh", "Hughes", "Wiremu", "Mitchell", "Park", "Foster", "Henare",
    "McDonald", "Sharma", "O'Sullivan", "Lee", "Barrett", "Turner", "Campbell", "Clarke",
    "Richards", "Patel", "Thompson", "Cooper", "Singh", "Jenkins", "Harris", "Taylor",
    "Brown", "Wilson", "O'Brien", "Martin", "Young", "King", "White", "Robinson",
    "Wright", "Nguyen", "Stewart", "Kelly", "Davis", "Zhang", "Morgan", "Baker",
    "Scott", "Murray", "Wood", "Morris", "Gray", "Mason", "Bell", "Duncan",
    "Ross", "Fraser", "Hamilton", "Crawford", "Johnston", "Kaur", "Adams", "Gordon",
    "Stone", "Fox", "Blair", "Cole",
]

_JOB_TITLES = [
    "Steel Fabrication Manager", "Corrosion Engineer", "Maintenance Director",
    "Shipyard Operations Manager", "Procurement Specialist - Coatings",
    "Quality Control Manager", "Site Engineer", "Workshop Foreman",
    "Rust Prevention Specialist", "Materials Engineer", "Fabrication Supervisor",
    "Protective Coatings Inspector", "Plant Manager", "Supply Chain Manager",
    "Underground Mining Engineer", "Structural Engineer", "Asset Integrity Manager",
    "Project Engineer - Steel Structures", "Surface Preparation Supervisor",
    "Welding Inspector", "Operations Manager", "Workshop Manager",
    "Coating Application Technician", "Safety & Compliance Manager",
    "Procurement Manager - Industrial Coatings", "Production Supervisor",
    "Mining Operations Engineer", "Civil & Structural Lead", "Fleet Maintenance Manager",
    "Infrastructure Project Manager", "HSE Manager", "Marine Coatings Specialist",
    "Blast & Paint Supervisor", "Reliability Engineer", "Warehouse & Logistics Manager",
    "Technical Sales Manager - Coatings", "Workshop Superintendent",
    "Pipeline Integrity Engineer", "Contracts Manager", "Plant Maintenance Planner",
]

_COMPANIES = [
    ("Precision Steel WA", "Perth", "WA", "AU"),
    ("AusCoat Solutions", "Melbourne", "VIC", "AU"),
    ("Iron Range Mining", "Kalgoorlie", "WA", "AU"),
    ("Pacific Dockyard NZ", "Wellington", "Wellington", "NZ"),
    ("BHP Nickel West", "Perth", "WA", "AU"),
    ("Steel Blue Fabrications", "Geelong", "VIC", "AU"),
    ("Fortescue Metals Group", "Port Hedland", "WA", "AU"),
    ("Kiwi Steel Structures", "Auckland", "Auckland", "NZ"),
    ("Coastal Engineering VIC", "Frankston", "VIC", "AU"),
    ("Rio Tinto Iron Ore", "Newman", "WA", "AU"),
    ("Murray Steel Works", "Ballarat", "VIC", "AU"),
    ("Downer Group", "Perth", "WA", "AU"),
    ("Tasman Steel NZ", "Christchurch", "Canterbury", "NZ"),
    ("BlueScope Steel", "Melbourne", "VIC", "AU"),
    ("Newmont Boddington", "Boddington", "WA", "AU"),
    ("Civmec Construction", "Henderson", "WA", "AU"),
    ("Monadelphous Group", "Perth", "WA", "AU"),
    ("NZ Steel", "Glenbrook", "Waikato", "NZ"),
    ("Southern Cross Fabrication", "Bunbury", "WA", "AU"),
    ("OneSteel Metalcentre", "Dandenong", "VIC", "AU"),
    ("CSBP Chemicals", "Kwinana", "WA", "AU"),
    ("Worley Parsons", "Perth", "WA", "AU"),
    ("Fletcher Steel NZ", "Hamilton", "Waikato", "NZ"),
    ("Austal Ships", "Henderson", "WA", "AU"),
    ("Transfield Services", "Sydney", "NSW", "AU"),
    ("John Holland Group", "Melbourne", "VIC", "AU"),
    ("Pilbara Minerals", "Pilgangoora", "WA", "AU"),
    ("South32 Worsley Alumina", "Collie", "WA", "AU"),
    ("Steel & Tube NZ", "Lower Hutt", "Wellington", "NZ"),
    ("Valmec Engineering", "Welshpool", "WA", "AU"),
]


def _generate_demo_results(keywords: list[str], location: str, max_results: int) -> list[dict]:
    """Generate realistic demo scraping results for any requested count."""

    logger.info(f"Generating {max_results} demo results...")

    # Use a seeded RNG so the same keywords produce consistent results
    seed = hash(tuple(sorted(keywords))) & 0xFFFFFFFF
    rng = random.Random(seed)

    results = []
    used_names = set()

    for _ in range(max_results):
        # Pick a unique first+last combo
        for _attempt in range(50):
            first = rng.choice(_FIRST_NAMES)
            last = rng.choice(_LAST_NAMES)
            if (first, last) not in used_names:
                used_names.add((first, last))
                break

        title = rng.choice(_JOB_TITLES)
        company, city, state, country = rng.choice(_COMPANIES)
        slug = f"{first.lower()}-{last.lower().replace(chr(39), '')}-{rng.randint(100,999)}"

        results.append({
            "first_name": first,
            "last_name": last,
            "job_title": title,
            "company_name": company,
            "location_city": city,
            "location_state": state,
            "location_country": country,
            "linkedin_url": f"https://linkedin.com/in/{slug}",
        })

    # Simulate scraping delay with logging
    for i, result in enumerate(results):
        delay = rng.uniform(0.05, 0.15)
        time.sleep(delay)
        logger.info(f"  [DEMO {i+1}/{len(results)}] {result['first_name']} {result['last_name']} - {result['job_title']}")

    logger.info(f"Demo scrape complete: {len(results)} leads generated")
    return results
