from urllib.parse import urlparse


def extract_domain_from_url(url: str) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    parsed = urlparse(url)
    domain = parsed.netloc
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def build_email_guess(first_name: str, last_name: str, domain: str) -> list[str]:
    first = first_name.lower().strip()
    last = last_name.lower().strip()
    return [
        f"{first}.{last}@{domain}",
        f"{first[0]}{last}@{domain}",
        f"{first}@{domain}",
        f"{first}_{last}@{domain}",
        f"{first}{last[0]}@{domain}",
    ]
