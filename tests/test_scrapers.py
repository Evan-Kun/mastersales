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


def test_linkedin_scraper_is_base_scraper():
    from scraper.linkedin import LinkedInScraper
    scraper = LinkedInScraper.__new__(LinkedInScraper)
    assert isinstance(scraper, BaseScraper)
    assert scraper.slug == "linkedin"
    assert scraper.uses_browser is True
    assert scraper.requires_auth is True


def test_linkedin_demo_results():
    from scraper.linkedin import LinkedInScraper
    scraper = LinkedInScraper.__new__(LinkedInScraper)
    results = scraper.generate_demo_results({"keywords": ["steel", "corrosion"], "max_results": 5})
    assert len(results) == 5
    assert all(r["source_name"] == "LinkedIn" for r in results)
    assert all(r["first_name"] and r["last_name"] for r in results)
    assert all(r["company_name"] for r in results)


def test_nz_tenders_scraper_interface():
    from scraper.tenders_nz import GETSScraper
    from scraper.base import BaseScraper
    scraper = GETSScraper()
    assert isinstance(scraper, BaseScraper)
    assert scraper.slug == "tenders_nz"
    assert scraper.requires_auth is False

def test_nz_tenders_demo_results():
    from scraper.tenders_nz import GETSScraper
    results = GETSScraper().generate_demo_results({"keywords": ["steel"], "max_results": 5})
    assert len(results) == 5
    assert all(r["source_name"] == "GETS" for r in results)
    assert all(r["location_country"] == "NZ" for r in results)


def test_trade_shows_scraper_interface():
    from scraper.trade_shows import TradeShowScraper
    from scraper.base import BaseScraper
    scraper = TradeShowScraper()
    assert isinstance(scraper, BaseScraper)
    assert scraper.slug == "trade_shows"
    assert scraper.uses_browser is True

def test_trade_shows_demo_with_events():
    from scraper.trade_shows import TradeShowScraper, HARDCODED_EVENTS
    results = TradeShowScraper().generate_demo_results({"keywords": ["steel"], "max_results": 5})
    assert len(results) == 5
    assert all("Trade Show" in r["source_name"] for r in results)
    assert "aca_conf" in HARDCODED_EVENTS
    assert "austmine" in HARDCODED_EVENTS


def test_au_tenders_scraper_interface():
    from scraper.tenders_au import AusTenderScraper
    scraper = AusTenderScraper()
    assert isinstance(scraper, BaseScraper)
    assert scraper.slug == "tenders_au"
    assert scraper.requires_auth is False
    assert scraper.uses_browser is True


def test_au_tenders_demo_results():
    from scraper.tenders_au import AusTenderScraper
    results = AusTenderScraper().generate_demo_results({
        "keywords": ["steel"], "max_results": 5,
    })
    assert len(results) == 5
    assert all(r["source_name"] == "AusTender" for r in results)
