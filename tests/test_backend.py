from fastapi.testclient import TestClient
from backend.main import app
from services.sandbox.runner import SandboxRunner

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "gcp_project" in data


def test_telegram_webhook_instant_ack():
    payload = {
        "update_id": 1001,
        "message": {
            "message_id": 1,
            "chat": {"id": 12345678},
            "text": "Сравни видео @GoogleCloud"
        }
    }
    response = client.post("/api/telegram/webhook", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True


def test_ai_analyze_endpoint():
    payload = {
        "query": "Сравни просмотры последних видео @GoogleCloud"
    }
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "summary_text" in data
    assert "plotly_spec" in data
    assert data["videos_analyzed"] > 0


def test_competitors_list_and_add():
    # 1. List competitors
    resp = client.get("/api/competitors")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

    # 2. Add competitor
    add_payload = {"channel_url_or_handle": "@MKBHD"}
    add_resp = client.post("/api/competitors", json=add_payload)
    assert add_resp.status_code == 200
    assert add_resp.json()["status"] == "REGISTERED"


def test_cron_track_competitors():
    response = client.post("/api/cron/track-competitors")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert "digest" in data


def test_sandbox_runner_matplotlib_png():
    runner = SandboxRunner(default_timeout_sec=5.0)
    code = """
plt.figure(figsize=(6, 3))
plt.bar(df['title'], df['view_count'])
plt.title('Test Chart')
"""
    data = [
        {"title": "Video 1", "view_count": 100},
        {"title": "Video 2", "view_count": 250}
    ]
    res = runner.execute(code=code, data=data, output_format="matplotlib")
    assert res["status"] == "SUCCESS"
    assert res["png_base64"] is not None
    assert len(res["png_base64"]) > 50


def test_sandbox_runner_plotly_json():
    runner = SandboxRunner(default_timeout_sec=5.0)
    code = """
import plotly.express as px
fig = px.bar(df, x='title', y='view_count')
"""
    data = [
        {"title": "Video A", "view_count": 500},
        {"title": "Video B", "view_count": 800}
    ]
    res = runner.execute(code=code, data=data, output_format="plotly")
    assert res["status"] == "SUCCESS"
    assert res["plotly_spec"] is not None
    assert "data" in res["plotly_spec"]
