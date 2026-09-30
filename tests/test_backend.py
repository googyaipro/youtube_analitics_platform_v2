import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.database import Base, get_db
from backend.main import app
from config.settings import get_settings
import backend.api.v1.endpoints.telegram as telegram_endpoint

from sqlalchemy.pool import StaticPool

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
Base.metadata.create_all(bind=test_engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def setup_teardown_db():
    app.dependency_overrides[get_db] = override_get_db
    orig_session = telegram_endpoint.SessionLocal
    telegram_endpoint.SessionLocal = TestingSessionLocal
    yield
    app.dependency_overrides.clear()
    telegram_endpoint.SessionLocal = orig_session

client = TestClient(app)
settings = get_settings()


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "database" in data


def test_telegram_webhook_auth_and_ack():
    payload = {
        "update_id": 1001,
        "message": {
            "message_id": 1,
            "chat": {"id": 12345678},
            "text": "/help"
        }
    }
    
    # 1. If webhook secret is configured, unauthorized requests should return 403
    secret = settings.TELEGRAM_WEBHOOK_SECRET
    if secret:
        unauth_resp = client.post("/api/v1/telegram/webhook", json=payload)
        assert unauth_resp.status_code == 403
        
        # Valid secret returns 200
        headers = {"X-Telegram-Bot-Api-Secret-Token": secret}
        auth_resp = client.post("/api/v1/telegram/webhook", json=payload, headers=headers)
        assert auth_resp.status_code == 200
        assert auth_resp.json()["ok"] is True
    else:
        resp = client.post("/api/v1/telegram/webhook", json=payload)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


def test_user_registration_and_language():
    import uuid
    random_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    reg_payload = {
        "email": random_email,
        "password": "SecurePassword123!",
        "full_name": "Test Runner"
    }
    resp = client.post("/api/v1/auth/register", json=reg_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Test get profile
    prof_resp = client.get("/api/v1/auth/me", headers=headers)
    assert prof_resp.status_code == 200
    assert prof_resp.json()["email"] == random_email

    # Test update language via PUT with JSON body
    lang_resp = client.put("/api/v1/auth/me/language", json={"language": "de"}, headers=headers)
    assert lang_resp.status_code == 200
    assert lang_resp.json()["language"] == "de"

    # Test update language via PATCH with JSON body
    lang_resp3 = client.patch("/api/v1/auth/me/language", json={"language": "ka"}, headers=headers)
    assert lang_resp3.status_code == 200
    assert lang_resp3.json()["language"] == "ka"


def test_gemini_explain_video_success_kwargs():
    from backend.services.gemini_service import GeminiService
    mock_video = {
        "title": "How to Build AI Agents",
        "channel_title": "AI Masterclass",
        "view_count": 50000,
        "channel_avg_views": 10000,
        "outlier_score": 5.0,
        "velocity_vph": 125.5,
        "engagement_rate_pct": 4.2
    }
    # 1. Calling with video_data
    res1 = GeminiService.explain_video_success(video_data=mock_video, target_language="en")
    assert "verdict" in res1
    assert "hook_analysis" in res1

    # 2. Calling with legacy video kwarg (must not raise TypeError)
    res2 = GeminiService.explain_video_success(video=mock_video, target_language="ru")
    assert "verdict" in res2
    assert "hook_analysis" in res2


def test_youtube_service_get_channel_details_interface():
    from backend.services.youtube_service import YouTubeService
    # Verify the method exists and handles invalid/empty key gracefully
    res = YouTubeService.get_channel_details("@nonexistent_channel_123456", "invalid_api_key")
    assert res is None


def test_cron_secret_protection():
    cron_secret = settings.CRON_SECRET or settings.TELEGRAM_WEBHOOK_SECRET
    if cron_secret:
        # Without secret -> 403
        resp = client.post("/api/v1/cron/dispatch-schedules")
        assert resp.status_code == 403

        # With secret -> 200
        headers = {"X-Cron-Secret": cron_secret}
        auth_resp = client.post("/api/v1/cron/dispatch-schedules", headers=headers)
        assert auth_resp.status_code == 200



def test_sandbox_runner_matplotlib_png():
    pytest.importorskip("matplotlib")
    from services.sandbox.runner import SandboxRunner
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
    pytest.importorskip("matplotlib")
    pytest.importorskip("plotly")
    from services.sandbox.runner import SandboxRunner
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


