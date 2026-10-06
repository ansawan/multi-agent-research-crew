import pytest
from fastapi.testclient import TestClient

from src import api, config

client = TestClient(api.app)
BRIEF = {"topic": "Test topic", "delivery_email": "a@example.com"}


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "test-key")
    api.jobs.clear()


def test_root_is_public():
    assert client.get("/").json()["status"] == "online"


def test_research_requires_api_key():
    assert client.post("/research", json=BRIEF).status_code == 401
    assert client.post("/research", json=BRIEF, headers={"X-API-Key": "wrong"}).status_code == 401


def test_server_without_api_key_rejects_requests(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "")
    assert client.post("/research", json=BRIEF, headers={"X-API-Key": ""}).status_code == 500


def test_research_validates_body():
    assert client.post("/research", json={}, headers={"X-API-Key": "test-key"}).status_code == 422


def test_research_starts_job(monkeypatch):
    monkeypatch.setattr(config, "validate_config", lambda: (True, "ok"))

    async def fake_job(job_id, input_data):
        api.jobs[job_id].update(status="completed", stage="done", report_markdown="# R", report_html="<h1>R</h1>")

    monkeypatch.setattr(api, "execute_crew_job", fake_job)
    headers = {"X-API-Key": "test-key"}
    job_id = client.post("/research", json=BRIEF, headers=headers).json()["job_id"]

    status = client.get(f"/status/{job_id}", headers=headers).json()
    assert status["status"] == "completed"
    assert client.get(f"/report/{job_id}", headers=headers).json()["report_markdown"] == "# R"
    assert client.get(f"/report/{job_id}/view").text == "<h1>R</h1>"


def test_unknown_job_returns_404():
    assert client.get("/status/nope", headers={"X-API-Key": "test-key"}).status_code == 404


def test_slugify():
    assert api.slugify("AI Chatbots: Pakistan & UAE!") == "ai-chatbots-pakistan-uae"
