import pytest
from fastapi.testclient import TestClient
from app import app


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def test_dashboard_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "MasterSales" in response.text
    assert "Total Leads" in response.text


def test_leads_page_loads(client):
    response = client.get("/leads")
    assert response.status_code == 200
    assert "Leads" in response.text


def test_leads_search(client):
    response = client.get("/leads?q=Mark")
    assert response.status_code == 200
    assert "Mark" in response.text


def test_leads_filter_by_status(client):
    response = client.get("/leads?status=New")
    assert response.status_code == 200


def test_lead_detail_loads(client):
    response = client.get("/leads/1")
    assert response.status_code == 200
    assert "Contact Information" in response.text


def test_lead_detail_404(client):
    response = client.get("/leads/9999")
    assert response.status_code == 404


def test_pipeline_page_loads(client):
    response = client.get("/pipeline")
    assert response.status_code == 200
    assert "Pipeline Board" in response.text


def test_scraper_page_loads(client):
    response = client.get("/scraper")
    assert response.status_code == 200
    assert "Lead Sourcing" in response.text


def test_scheduler_page_loads(client):
    response = client.get("/scheduler")
    assert response.status_code == 200
    assert "Meeting Scheduler" in response.text


def test_nurture_page_loads(client):
    response = client.get("/nurture")
    assert response.status_code == 200
    assert "Nurture Sequences" in response.text


def test_proposals_page_loads(client):
    response = client.get("/proposals")
    assert response.status_code == 200
    assert "Proposals" in response.text


def test_pipeline_move(client):
    response = client.post("/pipeline/move", data={"contact_id": 1, "new_status": "Contacted"})
    assert response.status_code == 200


def test_lead_update(client):
    response = client.post("/leads/1/update", data={"lead_status": "Qualified", "deal_value": 5000})
    assert response.status_code in [200, 303]
