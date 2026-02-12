from proposals.email_generator import render_email_proposal


def test_render_email_proposal():
    html = render_email_proposal(
        contact_name="John Smith",
        company_name="WA Steel Fabricators",
        products=[
            {"name": "CorrShield Base Coat", "description": "Zinc-rich primer", "quantity": "50L", "unit_price": 45.00, "total": 2250.00},
        ],
        total_price=2250.00,
        notes="Includes free shipping to Perth.",
    )
    assert "John Smith" in html
    assert "WA Steel Fabricators" in html
    assert "CorrShield Base Coat" in html
    assert "2,250" in html
