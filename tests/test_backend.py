from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "gcp_project" in data


def test_list_channels():
    response = client.get("/api/v1/channels")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_list_videos():
    response = client.get("/api/v1/videos")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_kpis():
    response = client.get("/api/v1/videos/kpis")
    assert response.status_code == 200
    data = response.json()
    assert "total_views" in data
    assert "engagement_rate_pct" in data


def test_ingestion_sync():
    payload = {
        "channel_identifier": "@GoogleCloud",
        "max_videos": 5
    }
    response = client.post("/api/v1/ingestion/sync", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert "channel_title" in data
    assert data["videos_synced"] > 0
