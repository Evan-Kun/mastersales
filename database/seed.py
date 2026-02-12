from sqlalchemy.orm import Session
from database.models import Company, Contact, NurtureSequence


def seed_demo_data(db: Session):
    """Seed the database with realistic demo data for Corrizon's ICP."""

    if db.query(Company).first():
        return

    companies_data = [
        {
            "company_name": "WA Steel Fabricators",
            "company_website": "wasteel.com.au",
            "company_industry": "Steel Fabrication",
            "company_size": "50-200",
            "company_revenue": "$5M-$20M",
            "company_location": "Perth, WA",
            "company_keywords": "steel,fabrication,mining,coating",
            "abn": "12345678901",
        },
        {
            "company_name": "Southern Cross Engineering",
            "company_website": "scengineering.com.au",
            "company_industry": "Engineering & Fabrication",
            "company_size": "20-50",
            "company_revenue": "$2M-$5M",
            "company_location": "Melbourne, VIC",
            "company_keywords": "engineering,steel,maintenance,protection",
            "abn": "23456789012",
        },
        {
            "company_name": "Pilbara Mining Services",
            "company_website": "pilbaramining.com.au",
            "company_industry": "Mining Services",
            "company_size": "200-500",
            "company_revenue": "$20M-$50M",
            "company_location": "Karratha, WA",
            "company_keywords": "mining,corrosion,rust,maintenance,salt",
            "abn": "34567890123",
        },
        {
            "company_name": "NZ Marine Engineering",
            "company_website": "nzmarine.co.nz",
            "company_industry": "Shipbuilding & Marine",
            "company_size": "10-20",
            "company_revenue": "$1M-$5M",
            "company_location": "Auckland, NZ",
            "company_keywords": "shipbuilding,marine,corrosion,salt,coating",
            "abn": "",
        },
        {
            "company_name": "VicSteel Constructions",
            "company_website": "vicsteel.com.au",
            "company_industry": "Steel Construction",
            "company_size": "50-200",
            "company_revenue": "$10M-$20M",
            "company_location": "Geelong, VIC",
            "company_keywords": "steel,construction,fabrication,zinc,paint",
            "abn": "56789012345",
        },
        {
            "company_name": "Outback Machinery",
            "company_website": "outbackmachinery.com.au",
            "company_industry": "Heavy Machinery",
            "company_size": "20-50",
            "company_revenue": "$2M-$10M",
            "company_location": "Kalgoorlie, WA",
            "company_keywords": "machinery,mining,rust,treatment,maintenance",
            "abn": "67890123456",
        },
        {
            "company_name": "Canterbury Steel Works",
            "company_website": "canterburysteel.co.nz",
            "company_industry": "Steel Fabrication",
            "company_size": "10-50",
            "company_revenue": "$1M-$5M",
            "company_location": "Christchurch, NZ",
            "company_keywords": "steel,fabrication,coating,undercoat",
            "abn": "",
        },
    ]

    companies = []
    for data in companies_data:
        company = Company(**data)
        db.add(company)
        companies.append(company)
    db.flush()

    contacts_data = [
        {"first_name": "Mark", "last_name": "Thompson", "job_title": "Operations Manager", "seniority_level": "Manager", "email_work": "mark.t@wasteel.com.au", "phone_work": "+61 8 9200 1234", "location_city": "Perth", "location_state": "WA", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/mark-thompson-wa", "lead_status": "New", "lead_source": "LinkedIn", "company": companies[0]},
        {"first_name": "Sarah", "last_name": "Chen", "job_title": "Procurement Director", "seniority_level": "Director", "email_work": "sarah.chen@wasteel.com.au", "phone_work": "+61 8 9200 1235", "location_city": "Perth", "location_state": "WA", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/sarah-chen-perth", "lead_status": "Contacted", "lead_source": "LinkedIn", "deal_value": 8000, "company": companies[0]},
        {"first_name": "David", "last_name": "Williams", "job_title": "General Manager", "seniority_level": "C-Suite", "email_work": "david@scengineering.com.au", "phone_mobile": "+61 412 345 678", "location_city": "Melbourne", "location_state": "VIC", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/david-williams-melb", "lead_status": "Qualified", "lead_source": "LinkedIn", "deal_value": 12000, "company": companies[1]},
        {"first_name": "Rachel", "last_name": "O'Brien", "job_title": "Site Maintenance Manager", "seniority_level": "Manager", "email_work": "rachel.obrien@pilbaramining.com.au", "phone_work": "+61 8 9100 5678", "location_city": "Karratha", "location_state": "WA", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/rachel-obrien-pilbara", "lead_status": "Proposal", "lead_source": "LinkedIn", "deal_value": 15000, "company": companies[2]},
        {"first_name": "James", "last_name": "Hartley", "job_title": "Chief Engineer", "seniority_level": "C-Suite", "email_work": "james@pilbaramining.com.au", "location_city": "Karratha", "location_state": "WA", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/james-hartley-mining", "lead_status": "Contacted", "lead_source": "LinkedIn", "company": companies[2]},
        {"first_name": "Aroha", "last_name": "Ngata", "job_title": "Workshop Manager", "seniority_level": "Manager", "email_work": "aroha@nzmarine.co.nz", "phone_work": "+64 9 300 1234", "location_city": "Auckland", "location_state": "Auckland", "location_country": "NZ", "linkedin_url": "https://linkedin.com/in/aroha-ngata-nz", "lead_status": "New", "lead_source": "LinkedIn", "company": companies[3]},
        {"first_name": "Peter", "last_name": "Rossi", "job_title": "Production Manager", "seniority_level": "Manager", "email_work": "peter.rossi@vicsteel.com.au", "phone_mobile": "+61 423 456 789", "location_city": "Geelong", "location_state": "VIC", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/peter-rossi-geelong", "lead_status": "Negotiation", "lead_source": "LinkedIn", "deal_value": 9500, "company": companies[4]},
        {"first_name": "Emma", "last_name": "Jacobs", "job_title": "Quality Assurance Lead", "seniority_level": "Manager", "email_work": "emma.j@vicsteel.com.au", "location_city": "Geelong", "location_state": "VIC", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/emma-jacobs-qa", "lead_status": "Qualified", "lead_source": "LinkedIn", "company": companies[4]},
        {"first_name": "Bruce", "last_name": "Keller", "job_title": "Owner / Director", "seniority_level": "Owner", "email_work": "bruce@outbackmachinery.com.au", "phone_mobile": "+61 400 111 222", "location_city": "Kalgoorlie", "location_state": "WA", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/bruce-keller-outback", "lead_status": "Won", "lead_source": "LinkedIn", "deal_value": 3500, "company": companies[5]},
        {"first_name": "Hemi", "last_name": "Parata", "job_title": "Fabrication Supervisor", "seniority_level": "Manager", "email_work": "hemi@canterburysteel.co.nz", "phone_work": "+64 3 400 5678", "location_city": "Christchurch", "location_state": "Canterbury", "location_country": "NZ", "linkedin_url": "https://linkedin.com/in/hemi-parata-nz", "lead_status": "New", "lead_source": "LinkedIn", "company": companies[6]},
        {"first_name": "Lisa", "last_name": "Tanaka", "job_title": "Maintenance Coordinator", "seniority_level": "Staff", "email_work": "lisa.t@pilbaramining.com.au", "location_city": "Newman", "location_state": "WA", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/lisa-tanaka-newman", "lead_status": "Contacted", "lead_source": "LinkedIn", "company": companies[2]},
        {"first_name": "Andrew", "last_name": "Clarke", "job_title": "Structural Engineer", "seniority_level": "Staff", "email_work": "andrew.c@scengineering.com.au", "location_city": "Melbourne", "location_state": "VIC", "location_country": "AU", "linkedin_url": "https://linkedin.com/in/andrew-clarke-eng", "lead_status": "New", "lead_source": "LinkedIn", "company": companies[1]},
    ]

    for data in contacts_data:
        company = data.pop("company")
        contact = Contact(**data, company_id=company.id)
        db.add(contact)

    sequences = [
        NurtureSequence(
            name="Steel Fabricator Introduction",
            description="Initial outreach sequence for steel fabrication companies",
            steps=[
                {"day_offset": 0, "subject": "Protecting Your Steel Assets", "body_template": "Hi {first_name},\n\nI noticed {company_name} works with steel fabrication and wanted to share how Corrizon's water-based anti-corrosion system is helping companies like yours save time and money on steel protection.\n\nUnlike traditional coatings, our system is environmentally friendly with minimal VOCs, requires less surface preparation, and provides superior protection.\n\nWould you be open to a quick 15-minute call to see if this could benefit your operations?\n\nBest regards,\nCorrizon Team"},
                {"day_offset": 3, "subject": "Quick Question About Your Coating Process", "body_template": "Hi {first_name},\n\nI wanted to follow up on my previous message. Many of our clients in {location_state} have told us their biggest pain points are:\n\n- Time-consuming surface preparation\n- VOC compliance costs\n- Coating failures in harsh environments\n\nOur system addresses all three. Would a brief case study be helpful?\n\nBest,\nCorrizon Team"},
                {"day_offset": 7, "subject": "Case Study: 40% Cost Reduction in Steel Protection", "body_template": "Hi {first_name},\n\nI wanted to share a quick case study from a {company_industry} company similar to {company_name}.\n\nThey switched to Corrizon's system and saw:\n- 40% reduction in coating costs\n- 60% less preparation time\n- Zero VOC compliance issues\n\nI'd love to show you how this could work for your operation. Free to chat this week?\n\nCorrizon Team"},
                {"day_offset": 14, "subject": "Final Thought on Corrosion Protection", "body_template": "Hi {first_name},\n\nI appreciate your time. If corrosion protection isn't a priority right now, no worries at all.\n\nIf anything changes, you can reach us at www.corrizon.com.au. We're always happy to do a free assessment.\n\nWishing {company_name} continued success.\n\nBest,\nCorrizon Team"},
            ],
        ),
        NurtureSequence(
            name="Post-Demo Follow-Up",
            description="Follow-up sequence after product demonstration",
            steps=[
                {"day_offset": 0, "subject": "Great Meeting Today!", "body_template": "Hi {first_name},\n\nThank you for taking the time to see our anti-corrosion system in action today. As discussed, I'll prepare a customised proposal for {company_name} based on your requirements.\n\nIn the meantime, please don't hesitate to reach out with any questions.\n\nBest,\nCorrizon Team"},
                {"day_offset": 2, "subject": "Your Customised Proposal from Corrizon", "body_template": "Hi {first_name},\n\nAs promised, please find attached your customised proposal for {company_name}.\n\nThe proposal includes our recommended system based on your specific environment and usage requirements. I've highlighted the key cost savings compared to your current approach.\n\nHappy to walk through any details - just let me know a good time.\n\nBest,\nCorrizon Team"},
                {"day_offset": 5, "subject": "Any Questions on the Proposal?", "body_template": "Hi {first_name},\n\nJust checking in to see if you've had a chance to review the proposal. I'm available this week if you'd like to discuss any aspects in detail.\n\nWe can also arrange a trial application on a small section if that would help your decision.\n\nBest,\nCorrizon Team"},
            ],
        ),
    ]

    for seq in sequences:
        db.add(seq)

    db.commit()
