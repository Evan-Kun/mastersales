import os
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from config import settings

proposal_env = Environment(loader=FileSystemLoader("proposals/templates"))


def generate_pdf_proposal(
    contact_name: str,
    company_name: str,
    products: list[dict],
    total_price: float,
    notes: str = "",
    proposal_number: str = None,
) -> str:
    if not proposal_number:
        proposal_number = f"COR-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    template = proposal_env.get_template("proposal.html")
    html_content = template.render(
        company=settings.company_name,
        website=settings.company_website,
        contact_name=contact_name,
        company_name=company_name,
        products=products,
        total_price=total_price,
        notes=notes,
        proposal_number=proposal_number,
        date=datetime.now().strftime("%d %B %Y"),
        differentiators=settings.key_differentiators,
    )

    output_dir = "output/proposals"
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, f"{proposal_number}.pdf")

    from weasyprint import HTML
    HTML(string=html_content).write_pdf(pdf_path)
    return pdf_path
