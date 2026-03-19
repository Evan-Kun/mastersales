from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TypedDict

class ScraperConfig(TypedDict, total=False):
    keywords: list[str]
    location: str
    max_results: int
    credentials: dict[str, str]
    date_from: str
    date_to: str
    states: list[str]
    event_urls: list[str]
    events: list[str]

class ScraperResult(TypedDict):
    first_name: str
    last_name: str
    job_title: str | None
    company_name: str
    company_domain: str | None
    linkedin_url: str | None
    location_city: str | None
    location_state: str | None
    location_country: str | None
    source_url: str | None
    source_name: str

class BaseScraper(ABC):
    name: str = ""
    slug: str = ""
    requires_auth: bool = False
    credential_fields: list[dict] = []
    uses_browser: bool = False

    @abstractmethod
    def scrape(self, config: ScraperConfig) -> list[ScraperResult]:
        ...

    @abstractmethod
    def generate_demo_results(self, config: ScraperConfig) -> list[ScraperResult]:
        ...

    def validate_credentials(self, credentials: dict) -> bool:
        return True
