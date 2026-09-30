import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import get_current_user, encrypt_secret, decrypt_secret
from backend.models.user import User
from backend.schemas.auth import UserKeysUpdate, VerifyKeyRequest, VerifyKeyResponse, TelegramLinkResponse
from backend.services.youtube_service import YouTubeService
from backend.services.gemini_service import GeminiService
from config.settings import get_settings

router = APIRouter(prefix="/user", tags=["User Settings & BYOK"])
settings = get_settings()


@router.put("/keys")
def update_api_keys(
    keys_in: UserKeysUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save encrypted YouTube and Gemini API keys and automatically verify them."""
    if keys_in.youtube_api_key is not None:
        clean_yt = keys_in.youtube_api_key.strip()
        if clean_yt:
            current_user.youtube_api_key_encrypted = encrypt_secret(clean_yt)
            is_valid, _ = YouTubeService.verify_api_key(clean_yt)
            current_user.youtube_api_key_valid = is_valid
        else:
            current_user.youtube_api_key_encrypted = None
            current_user.youtube_api_key_valid = False

    if keys_in.gemini_api_key is not None:
        clean_gem = keys_in.gemini_api_key.strip()
        if clean_gem:
            current_user.gemini_api_key_encrypted = encrypt_secret(clean_gem)
            is_valid, _ = GeminiService.verify_api_key(
                clean_gem,
                user_id=current_user.id,
                user_email=current_user.email,
                db=db
            )
            current_user.gemini_api_key_valid = is_valid
        else:
            current_user.gemini_api_key_encrypted = None
            current_user.gemini_api_key_valid = False

    db.commit()
    db.refresh(current_user)
    return {
        "status": "SUCCESS",
        "message": "API keys saved and verified successfully.",
        "youtube_api_key_valid": current_user.youtube_api_key_valid,
        "gemini_api_key_valid": current_user.gemini_api_key_valid,
        "has_youtube_key": bool(current_user.youtube_api_key_encrypted),
        "has_gemini_key": bool(current_user.gemini_api_key_encrypted)
    }


@router.post("/verify-key", response_model=VerifyKeyResponse)
def verify_key(
    req: VerifyKeyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Test and verify YouTube or Gemini API key.
    Updates validity status in user profile upon success.
    """
    if req.key_type == "youtube":
        key_to_test = req.api_key or decrypt_secret(current_user.youtube_api_key_encrypted)
        if not key_to_test:
            raise HTTPException(status_code=400, detail="No YouTube API key provided or saved.")

        is_valid, message = YouTubeService.verify_api_key(key_to_test)
        if is_valid:
            if req.api_key:
                current_user.youtube_api_key_encrypted = encrypt_secret(req.api_key)
            current_user.youtube_api_key_valid = True
            db.commit()

        return VerifyKeyResponse(
            key_type="youtube",
            is_valid=is_valid,
            message=message,
            quota_available=is_valid
        )

    elif req.key_type == "gemini":
        key_to_test = req.api_key or decrypt_secret(current_user.gemini_api_key_encrypted)
        if not key_to_test:
            raise HTTPException(status_code=400, detail="No Gemini API key provided or saved.")

        is_valid, message = GeminiService.verify_api_key(
            key_to_test,
            user_id=current_user.id,
            user_email=current_user.email,
            db=db
        )
        if is_valid:
            if req.api_key:
                current_user.gemini_api_key_encrypted = encrypt_secret(req.api_key)
            current_user.gemini_api_key_valid = True
            db.commit()

        return VerifyKeyResponse(
            key_type="gemini",
            is_valid=is_valid,
            message=message,
            quota_available=is_valid
        )

    raise HTTPException(status_code=400, detail="Invalid key_type")


from backend.services.telegram_service import TelegramService


@router.post("/telegram-link", response_model=TelegramLinkResponse)
def generate_telegram_link(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate a one-time link to bind Telegram account to user profile."""
    bot_token = settings.TELEGRAM_BOT_TOKEN
    if not bot_token or " " in bot_token:
        raise HTTPException(
            status_code=400,
            detail="TELEGRAM_BOT_TOKEN is not configured in server environment. Please contact administrator."
        )

    link_code = secrets.token_hex(8)
    current_user.telegram_link_code = link_code
    db.commit()
    db.refresh(current_user)

    bot_info = TelegramService.get_bot_info()
    if bot_info and bot_info.get("username"):
        bot_username = bot_info.get("username")
        settings.TELEGRAM_BOT_USERNAME = bot_username
    else:
        bot_username = (settings.TELEGRAM_BOT_USERNAME or "").lstrip("@")

    link_url = f"https://t.me/{bot_username}?start={link_code}" if bot_username else f"https://t.me/?start={link_code}"

    return TelegramLinkResponse(
        link_url=link_url,
        code=link_code,
        expires_in_seconds=600
    )


@router.post("/telegram-test")
def send_telegram_test(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send an instant test notification to verified user's Telegram."""
    if not current_user.telegram_chat_id:
        raise HTTPException(
            status_code=400,
            detail="Telegram account is not linked. Please link your Telegram first."
        )

    lang = current_user.language or "en"
    dash_url = settings.DASHBOARD_URL.rstrip("/")
    test_msgs = {
        "ru": (
            f"🔔 **YouTube Analytics Platform — Тестовое уведомление**\n\n"
            f"Здравствуйте, **{current_user.email}**!\n"
            f"Ваш Telegram успешно подключен к платформе [{dash_url}]({dash_url}).\n\n"
            f"Сюда будут приходить ежедневные executive-дайджесты и оповещения об аномалиях по вашим наборам каналов."
        ),
        "en": (
            f"🔔 **YouTube Analytics Platform — Test Notification**\n\n"
            f"Hello, **{current_user.email}**!\n"
            f"Your Telegram account is connected to [{dash_url}]({dash_url}).\n\n"
            f"You will receive daily AI digests and viral anomaly alerts for your channel sets in this chat."
        ),
        "de": (
            f"🔔 **YouTube Analytics Platform — Testbenachrichtigung**\n\n"
            f"Hallo, **{current_user.email}**!\n"
            f"Ihr Telegram-Konto ist mit [{dash_url}]({dash_url}) verknüpft.\n\n"
            f"Sie erhalten tägliche KI-Digests und Warnungen zu viralen Anomalien für Ihre Kanal-Sets in diesem Chat."
        ),
        "fi": (
            f"🔔 **YouTube Analytics Platform — Testi-ilmoitus**\n\n"
            f"Hei, **{current_user.email}**!\n"
            f"Telegram-tilisi on yhdistetty alustaan [{dash_url}]({dash_url}).\n\n"
            f"Saat päivittäiset tekoäly-yhteenvedot ja viraalihälytykset kanavaseteistäsi tähän chattiin."
        ),
        "ka": (
            f"🔔 **YouTube Analytics Platform — სატესტო შეტყობინება**\n\n"
            f"მოგესალმებით, **{current_user.email}**!\n"
            f"თქვენი Telegram ანგარიში დაკავშირებულია [{dash_url}]({dash_url})-თან.\n\n"
            f"აქ მიიღებთ ყოველდღიურ AI დაიჯესტებს და ვირუსული ანომალიების შეტყობინებებს."
        ),
    }
    msg = test_msgs.get(lang) or test_msgs["en"]
    success = TelegramService.send_message(current_user.telegram_chat_id, msg)
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to send test message via Telegram Bot API. Please check bot permissions."
        )

    return {"success": True, "message": "Test notification delivered successfully."}
