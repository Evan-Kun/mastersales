from scraper.base import BaseScraper


def test_aca_scraper_interface():
    from scraper.aca import ACAScraper
    scraper = ACAScraper()
    assert isinstance(scraper, BaseScraper)
    assert scraper.slug == "aca"
    assert scraper.requires_auth is False

def test_aca_demo_results():
    from scraper.aca import ACAScraper
    scraper = ACAScraper()
    results = scraper.generate_demo_results({"keywords": ["corrosion"], "max_results": 5})
    assert len(results) == 5
    assert all(r["source_name"] == "ACA" for r in results)


def test_ampp_scraper_interface():
    from scraper.ampp import AMPPScraper
    scraper = AMPPScraper()
    assert isinstance(scraper, BaseScraper)
    assert scraper.slug == "ampp"
    assert scraper.requires_auth is False

def test_ampp_demo_results():
    from scraper.ampp import AMPPScraper
    results = AMPPScraper().generate_demo_results({"keywords": ["coating"], "max_results": 5})
    assert len(results) == 5
    assert all(r["source_name"] == "AMPP" for r in results)
