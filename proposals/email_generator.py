from jinja2 import Environment, FileSystemLoader
from config import settings

proposal_env = Environment(loader=FileSystemLoader("proposals/templates"))


def render_email_proposal(
    contact_name: str,
    company_name: str,
    products: list[dict],
    total_price: float,
    notes: str = "",
) -> str:
    template = proposal_env.get_template("email.html")
    return template.render(
        company=settings.company_name,
        website=settings.company_website,
        contact_name=contact_name,
        company_name=company_name,
        products=products,
        total_price=total_price,
        notes=notes,
        differentiators=settings.key_differentiators,
    )
