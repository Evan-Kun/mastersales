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
