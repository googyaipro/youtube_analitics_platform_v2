import os
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.database import Base
from backend.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    encrypt_secret,
    decrypt_secret,
)
from backend.models.user import User
from backend.models.channel_set import ChannelSet
from backend.models.channel import Channel
from backend.models.video_metric import VideoMetric
from backend.services.analytics_service import AnalyticsService
from backend.services.scheduler_service import SchedulerService
from backend.services.telegram_service import TelegramService
from dashboard.utils.i18n import LOCALES_DIR, SUPPORTED_LANGUAGES


@pytest.fixture(scope="module")
def db_session():
    # In-memory test sqlite database
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()


def test_security_hashing_and_jwt():
    # 1. Password hashing
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False

    # 2. JWT token creation and decoding
    user_id = "test-user-uuid-1234"
    token = create_access_token(user_id=user_id)
    assert isinstance(token, str) and len(token) > 20

    decoded_id = decode_access_token(token)
    assert decoded_id == user_id


def test_byok_encryption():
    raw_key = "AIzaSyTestApiKeyForYouTube1234567890"
    encrypted = encrypt_secret(raw_key)
    assert encrypted is not None
    assert encrypted != raw_key

    decrypted = decrypt_secret(encrypted)
    assert decrypted == raw_key


def test_user_and_channel_sets(db_session):
    # Create user
    user = User(
        email="developer@oxyjet.win",
        hashed_password=hash_password("DevPassword2026!"),
        full_name="Alex Developer",
        language="fi",
        youtube_api_key_encrypted=encrypt_secret("AIzaFakeYoutubeKey"),
        gemini_api_key_encrypted=encrypt_secret("AIzaFakeGeminiKey"),
        youtube_api_key_valid=True,
        gemini_api_key_valid=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None

    # Create 2 independent channel sets (Tech & Gaming)
    tech_set = ChannelSet(
        user_id=user.id,
        name="Tech Innovators",
        description="Monitoring AI and gadget channels",
        schedule_time="12:00",
        schedule_timezone="Europe/Helsinki",
        schedule_days="mon,tue,wed,thu,fri",
        schedule_enabled=True
    )
    gaming_set = ChannelSet(
        user_id=user.id,
        name="Gaming Streamers",
        description="Top twitch and youtube gamers",
        schedule_time="18:00",
        schedule_timezone="Europe/Berlin",
        schedule_days="sat,sun",
        schedule_enabled=True
    )
    db_session.add_all([tech_set, gaming_set])
    db_session.commit()

    # User selects Tech as active set
    user.active_set_id = tech_set.id
    db_session.commit()

    sets = db_session.query(ChannelSet).filter(ChannelSet.user_id == user.id).all()
    assert len(sets) == 2
    assert user.active_set_id == tech_set.id


def test_analytics_engine_and_window_functions(db_session):
    user = db_session.query(User).filter(User.email == "developer@oxyjet.win").first()
    tech_set = db_session.query(ChannelSet).filter(ChannelSet.user_id == user.id, ChannelSet.name == "Tech Innovators").first()

    # Add a channel to tech set
    channel = Channel(
        user_id=user.id,
        set_id=tech_set.id,
        channel_id="UC_x5XG1OV2P6uZZ5FSM9Ttw",
        title="Tech Guy",
        subscriber_count=100000,
        view_count=5000000
    )
    db_session.add(channel)
    db_session.commit()

    # Add 3 videos with different metrics to test window functions and outlier scoring
    now = datetime.now(timezone.utc)
    v1 = VideoMetric(
        user_id=user.id,
        set_id=tech_set.id,
        video_id="vid_normal",
        channel_id=channel.channel_id,
        channel_title=channel.title,
        title="Normal Tech Review",
        view_count=10000,
        like_count=500,
        comment_count=50,
        published_at=now - timedelta(hours=20),
        extracted_at=now
    )
    v2 = VideoMetric(
        user_id=user.id,
        set_id=tech_set.id,
        video_id="vid_viral_hit",
        channel_id=channel.channel_id,
        channel_title=channel.title,
        title="Revolutionary AI Release (Breakthrough!)",
        view_count=100000,  # High outlier relative to channel average
        like_count=5500,
        comment_count=800,
        published_at=now - timedelta(hours=10),
        extracted_at=now
    )
    db_session.add_all([v1, v2])
    db_session.commit()

    enriched = AnalyticsService.get_set_enriched_videos(db_session, user.id, tech_set.id, limit=10)
    assert len(enriched) == 2

    viral_vid = next(v for v in enriched if v["video_id"] == "vid_viral_hit")
    assert viral_vid["outlier_score"] >= 1.5
    assert any("Выше нормы" in badge or "Хит" in badge for badge in viral_vid["badges"])
    assert viral_vid["velocity_vph"] > 0
    assert viral_vid["engagement_rate_pct"] > 0

    kpis = AnalyticsService.get_set_kpis(db_session, user.id, tech_set.id)
    assert kpis["total_channels"] == 1
    assert kpis["total_videos"] == 2
    assert kpis["total_views"] == 110000
    assert kpis["viral_hits_count"] >= 1


def test_i18n_locales_completeness():
    required_langs = ["ru", "en", "de", "fi", "ka"]
    
    # Load base Russian dictionary
    ru_path = LOCALES_DIR / "ru.json"
    assert ru_path.exists(), "ru.json must exist"
    with open(ru_path, "r", encoding="utf-8") as f:
        base_keys = set(json.load(f).keys())

    for lang in required_langs:
        lang_path = LOCALES_DIR / f"{lang}.json"
        assert lang_path.exists(), f"Locale file {lang}.json must exist"
        with open(lang_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            missing_keys = base_keys - set(data.keys())
            assert not missing_keys, f"Locale {lang}.json is missing keys: {missing_keys}"


def test_telegram_commands_and_linking(db_session):
    user = db_session.query(User).filter(User.email == "developer@oxyjet.win").first()
    
    # Simulate linking code generation
    user.telegram_link_code = "tg_link_code_9999"
    db_session.commit()

    # 1. Telegram /start with valid code
    update_link = {
        "message": {
            "chat": {"id": 123456789},
            "text": "/start tg_link_code_9999",
            "from": {"language_code": "fi"}
        }
    }
    success = TelegramService.handle_webhook_update(db_session, update_link)
    assert success is True

    db_session.refresh(user)
    assert user.telegram_chat_id == "123456789"
    assert user.telegram_link_code is None

    # 2. Telegram /sets command
    update_sets = {
        "message": {
            "chat": {"id": 123456789},
            "text": "/sets"
        }
    }
    assert TelegramService.handle_webhook_update(db_session, update_sets) is True

    # 3. Telegram /top command
    update_top = {
        "message": {
            "chat": {"id": 123456789},
            "text": "/top"
        }
    }
    assert TelegramService.handle_webhook_update(db_session, update_top) is True

    # 4. Telegram /lang de command
    update_lang = {
        "message": {
            "chat": {"id": 123456789},
            "text": "/lang de"
        }
    }
    assert TelegramService.handle_webhook_update(db_session, update_lang) is True
    db_session.refresh(user)
    assert user.language == "de"


def test_api_endpoints_integration():
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.core.database import init_db

    init_db()

    with TestClient(app) as client:
        # Health check
        res_health = client.get("/health")
        assert res_health.status_code == 200
        assert res_health.json()["status"] == "healthy"

        # Register new user
        user_email = f"api_test_{int(datetime.now().timestamp())}@example.com"
        res_reg = client.post("/api/v1/auth/register", json={
            "email": user_email,
            "password": "Password123!",
            "full_name": "API Tester",
            "language": "en"
        })
        assert res_reg.status_code == 201
        data = res_reg.json()
        assert "access_token" in data
        token = data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # /auth/me
        res_me = client.get("/api/v1/auth/me", headers=headers)
        assert res_me.status_code == 200
        assert res_me.json()["email"] == user_email

        # /channel-sets
        res_sets = client.get("/api/v1/channel-sets", headers=headers)
        assert res_sets.status_code == 200
        assert len(res_sets.json()) >= 1  # Default set was automatically created on registration!

        # Create new set
        res_new_set = client.post("/api/v1/channel-sets", json={
            "name": "Crypto Alpha",
            "description": "Bitcoin & Ethereum analytics",
            "schedule_time": "09:00",
            "schedule_timezone": "UTC",
            "schedule_days": "mon,wed,fri",
            "schedule_enabled": True
        }, headers=headers)
        assert res_new_set.status_code == 201
        set_id = res_new_set.json()["id"]

        # Activate set
        res_act = client.post(f"/api/v1/channel-sets/{set_id}/activate", headers=headers)
        assert res_act.status_code == 200
        assert res_act.json()["active_set_id"] == set_id

        # /videos/kpis
        res_kpis = client.get("/api/v1/videos/kpis", headers=headers)
        assert res_kpis.status_code == 200
        assert "total_channels" in res_kpis.json()
