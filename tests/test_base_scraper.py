from scraper.base import ScraperResult, ScraperConfig, BaseScraper

def test_scraper_result_has_required_fields():
    result: ScraperResult = {
        "first_name": "John", "last_name": "Smith", "job_title": "Engineer",
        "company_name": "BHP", "company_domain": "bhp.com", "linkedin_url": None,
        "location_city": "Perth", "location_state": "WA", "location_country": "AU",
        "source_url": "https://example.com/page", "source_name": "ACA",
    }
    assert result["first_name"] == "John"
    assert result["source_name"] == "ACA"
    assert result["company_name"] == "BHP"

def test_scraper_config_accepts_partial():
    config: ScraperConfig = {"keywords": ["steel", "corrosion"], "location": "Australia", "max_results": 20}
    assert config["keywords"] == ["steel", "corrosion"]

def test_base_scraper_cannot_be_instantiated():
    import pytest
    with pytest.raises(TypeError):
        BaseScraper()

def test_contact_has_source_url_field():
    from database.models import Contact
    assert hasattr(Contact, "source_url")

def test_company_has_domain_field():
    from database.models import Company
    assert hasattr(Company, "company_domain")

def test_contact_lead_source_accepts_long_names():
    from database.models import Contact
    col = Contact.__table__.columns["lead_source"]
    assert col.type.length >= 100


# --- search_engine orchestrator tests ---

from scraper.base import BaseScraper, ScraperConfig, ScraperResult

class FakeScraperA(BaseScraper):
    name = "Fake A"; slug = "fake_a"; requires_auth = False; uses_browser = False
    def scrape(self, config):
        return [{"first_name": "John", "last_name": "Smith", "job_title": "Eng",
                 "company_name": "BHP", "company_domain": None, "linkedin_url": None,
                 "location_city": "Perth", "location_state": "WA", "location_country": "AU",
                 "source_url": "https://a.com", "source_name": "Fake A"}]
    def generate_demo_results(self, config): return self.scrape(config)

class FakeScraperB(BaseScraper):
    name = "Fake B"; slug = "fake_b"; requires_auth = False; uses_browser = False
    def scrape(self, config):
        return [
            {"first_name": "John", "last_name": "Smith", "job_title": "Engineer",
             "company_name": "BHP", "company_domain": "bhp.com", "linkedin_url": None,
             "location_city": "Perth", "location_state": "WA", "location_country": "AU",
             "source_url": "https://b.com", "source_name": "Fake B"},
            {"first_name": "Jane", "last_name": "Doe", "job_title": "PM",
             "company_name": "Rio Tinto", "company_domain": None, "linkedin_url": None,
             "location_city": "Sydney", "location_state": "NSW", "location_country": "AU",
             "source_url": "https://b.com/2", "source_name": "Fake B"},
        ]
    def generate_demo_results(self, config): return self.scrape(config)

def test_dedup_merges_cross_source():
    from scraper.search_engine import dedup_results
    results = FakeScraperA().scrape({}) + FakeScraperB().scrape({})
    deduped = dedup_results(results)
    assert len(deduped) == 2
    john = [r for r in deduped if r["first_name"] == "John"][0]
    assert john["company_domain"] == "bhp.com"
    assert "Fake A" in john["source_name"] and "Fake B" in john["source_name"]

def test_dedup_different_companies_not_merged():
    from scraper.search_engine import dedup_results
    results = [
        {"first_name": "John", "last_name": "Smith", "job_title": "Eng",
         "company_name": "BHP", "company_domain": None, "linkedin_url": None,
         "location_city": None, "location_state": None, "location_country": None,
         "source_url": None, "source_name": "A"},
        {"first_name": "John", "last_name": "Smith", "job_title": "Mgr",
         "company_name": "Rio Tinto", "company_domain": None, "linkedin_url": None,
         "location_city": None, "location_state": None, "location_country": None,
         "source_url": None, "source_name": "B"},
    ]
    deduped = dedup_results(results)
    assert len(deduped) == 2

def test_run_scrape_multi_source(monkeypatch):
    from scraper import search_engine
    monkeypatch.setattr(search_engine, "SCRAPERS", {"fake_a": FakeScraperA, "fake_b": FakeScraperB})
    results, status = search_engine.run_scrape(
        sources=["fake_a", "fake_b"], keywords=["steel"], location="Australia",
        max_results=20, credentials={}, source_configs={},
    )
    assert len(results) == 2
    assert status["total_found"] >= 2

def test_cancel_and_is_cancelled():
    from scraper.search_engine import cancel_scrape, is_cancelled, _cancel_event
    _cancel_event.clear()
    assert is_cancelled() is False
    cancel_scrape()
    assert is_cancelled() is True
    _cancel_event.clear()
