from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "MasterSales"
    database_url: str = "sqlite:///mastersales.db"
    debug: bool = True

    # Corrizon company details
    company_name: str = "Corrizon Australasia Pty Ltd"
    company_website: str = "www.corrizon.com.au"
    company_tagline: str = "High-tech steel treatment system to prevent corrosion"

    # ICP configuration
    target_countries: list[str] = ["AU", "NZ"]
    priority_states: list[str] = ["WA", "VIC"]
    industry_keywords: list[str] = [
        "steel", "corrosion", "rust", "protection", "coating",
        "zinc", "paint", "undercoat", "treatment", "maintenance",
        "salt", "mining", "engineering", "shipbuilding", "machinery",
        "fabrication", "application",
    ]
    deal_size_min: int = 500
    deal_size_max: int = 15000
    sales_cycle: str = "monthly"
    key_differentiators: list[str] = [
        "Environmentally friendly",
        "Water based",
        "Minimal VOCs",
        "Cost saving",
        "Time saving",
        "Better schedule control",
        "Easy application",
        "Reduced preparation",
        "Simple clean up",
        "Superior protection",
    ]

    # Corrizon products for proposal generation
    products: list[dict] = [
        {"name": "CorrShield Base Coat", "description": "Water-based zinc-rich primer for steel protection", "price_per_litre": 45.00},
        {"name": "CorrShield Top Coat", "description": "Environmental barrier top coat", "price_per_litre": 38.00},
        {"name": "CorrShield Complete System", "description": "Full 2-coat anti-corrosion system", "price_per_litre": 75.00},
        {"name": "Application Training", "description": "On-site application training (per day)", "price_per_litre": 1500.00},
        {"name": "Surface Assessment", "description": "Corrosion assessment and recommendation report", "price_per_litre": 800.00},
    ]

    # Scraper settings
    linkedin_email: str = ""
    linkedin_password: str = ""
    scrape_delay_min: float = 2.0
    scrape_delay_max: float = 5.0
    scrape_max_results: int = 50

    model_config = {"env_file": ".env"}


settings = Settings()
