from scraper.web_enricher import extract_domain_from_url, build_email_guess


def test_extract_domain():
    assert extract_domain_from_url("https://www.wasteel.com.au/about") == "wasteel.com.au"
    assert extract_domain_from_url("http://scengineering.com.au") == "scengineering.com.au"


def test_extract_domain_without_scheme():
    assert extract_domain_from_url("wasteel.com.au") == "wasteel.com.au"


def test_build_email_guess():
    guesses = build_email_guess("John", "Smith", "wasteel.com.au")
    assert "john.smith@wasteel.com.au" in guesses
    assert "jsmith@wasteel.com.au" in guesses
    assert "john@wasteel.com.au" in guesses
