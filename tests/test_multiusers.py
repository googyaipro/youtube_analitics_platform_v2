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

    # 3b. Telegram /digest command
    update_digest = {
        "message": {
            "chat": {"id": 123456789},
            "text": "/digest"
        }
    }
    assert TelegramService.handle_webhook_update(db_session, update_digest) is True

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

    # 5. Direct code message linking (without /start)
    user.telegram_chat_id = None
    user.telegram_link_code = "direct_token_123"
    db_session.commit()

    update_direct = {
        "message": {
            "chat": {"id": 987654321},
            "text": "code direct_token_123 please",
            "from": {"language_code": "ru"}
        }
    }
    assert TelegramService.handle_webhook_update(db_session, update_direct) is True
    db_session.refresh(user)
    assert user.telegram_chat_id == "987654321"
    assert user.telegram_link_code is None


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

        # /channel-sets/{set_id}/digest
        res_digest = client.get(f"/api/v1/channel-sets/{set_id}/digest", headers=headers)
        assert res_digest.status_code == 200
        digest_data = res_digest.json()
        assert "digest" in digest_data
        assert digest_data["set_id"] == set_id


def test_admin_endpoints_and_authorization():
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.core.database import init_db
    from config.settings import get_settings

    init_db()
    settings = get_settings()

    with TestClient(app) as client:
        ts = int(datetime.now().timestamp())
        admin_email = f"admin_{ts}@example.com"
        victim_email = f"victim_{ts}@example.com"

        # Register admin user
        r_admin = client.post("/api/v1/auth/register", json={
            "email": admin_email,
            "password": "AdminPassword123!",
            "full_name": "Chief Administrator"
        })
        assert r_admin.status_code == 201
        admin_data = r_admin.json()
        admin_token = admin_data["access_token"]
        admin_id = admin_data["user_id"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Register second regular user
        r_victim = client.post("/api/v1/auth/register", json={
            "email": victim_email,
            "password": "VictimPassword123!",
            "full_name": "Regular User"
        })
        assert r_victim.status_code == 201
        victim_data = r_victim.json()
        victim_token = victim_data["access_token"]
        victim_id = victim_data["user_id"]
        victim_headers = {"Authorization": f"Bearer {victim_token}"}

        # 1. Non-admin accessing admin endpoints must get 403
        r_unauth = client.get("/api/v1/admin/stats", headers=victim_headers)
        assert r_unauth.status_code == 403

        # 2. Regular user claims admin status via admin_secret
        r_claim = client.post("/api/v1/admin/claim", json={
            "admin_secret": settings.ADMIN_SECRET
        }, headers=admin_headers)
        assert r_claim.status_code == 200
        assert r_claim.json()["is_admin"] is True

        # 3. Admin stats
        r_stats = client.get("/api/v1/admin/stats", headers=admin_headers)
        assert r_stats.status_code == 200
        stats = r_stats.json()
        assert stats["total_users"] >= 2
        assert stats["active_users"] >= 2

        # 4. List users
        r_users = client.get("/api/v1/admin/users", headers=admin_headers)
        assert r_users.status_code == 200
        user_list = r_users.json()
        emails = [u["email"] for u in user_list]
        assert admin_email in emails
        assert victim_email in emails

        # 5. Prevent admin self-blocking or self-deletion
        r_self_block = client.post(f"/api/v1/admin/users/{admin_id}/toggle-active", headers=admin_headers)
        assert r_self_block.status_code == 400

        r_self_del = client.delete(f"/api/v1/admin/users/{admin_id}", headers=admin_headers)
        assert r_self_del.status_code == 400

        # 6. Block victim user
        r_block = client.post(f"/api/v1/admin/users/{victim_id}/toggle-active", headers=admin_headers)
        assert r_block.status_code == 200
        assert r_block.json()["is_active"] is False

        # Verify blocked user cannot log in or make API calls
        r_victim_call = client.get("/api/v1/auth/me", headers=victim_headers)
        assert r_victim_call.status_code == 400  # Inactive user

        # 7. Unblock victim user
        r_unblock = client.post(f"/api/v1/admin/users/{victim_id}/toggle-active", headers=admin_headers)
        assert r_unblock.status_code == 200
        assert r_unblock.json()["is_active"] is True

        # 8. Promote victim to admin
        r_promote = client.post(f"/api/v1/admin/users/{victim_id}/toggle-admin", headers=admin_headers)
        assert r_promote.status_code == 200
        assert r_promote.json()["is_admin"] is True

        # 9. Delete victim user
        r_del = client.delete(f"/api/v1/admin/users/{victim_id}", headers=admin_headers)
        assert r_del.status_code == 200
        assert r_del.json()["success"] is True

        # Verify victim no longer exists
        r_check_del = client.get("/api/v1/admin/users", headers=admin_headers)
        assert victim_email not in [u["email"] for u in r_check_del.json()]

        # 10. Check admin telegram status endpoint
        r_tg_status = client.get("/api/v1/admin/telegram-status", headers=admin_headers)
        assert r_tg_status.status_code == 200
        assert "bot_token_configured" in r_tg_status.json()

