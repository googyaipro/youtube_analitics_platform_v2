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
    """Save encrypted YouTube and Gemini API keys."""
    if keys_in.youtube_api_key is not None:
        clean_yt = keys_in.youtube_api_key.strip()
        current_user.youtube_api_key_encrypted = encrypt_secret(clean_yt) if clean_yt else None
        current_user.youtube_api_key_valid = False  # requires validation

    if keys_in.gemini_api_key is not None:
        clean_gem = keys_in.gemini_api_key.strip()
        current_user.gemini_api_key_encrypted = encrypt_secret(clean_gem) if clean_gem else None
        current_user.gemini_api_key_valid = False  # requires validation

    db.commit()
    return {
        "status": "SUCCESS",
        "message": "API keys saved successfully. Please run verification to activate."
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

        is_valid, message = GeminiService.verify_api_key(key_to_test)
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

    bot_username = (settings.TELEGRAM_BOT_USERNAME or "").lstrip("@")
    if not bot_username:
        bot_info = TelegramService.get_bot_info()
        if bot_info and bot_info.get("username"):
            bot_username = bot_info.get("username")
            settings.TELEGRAM_BOT_USERNAME = bot_username

    link_url = f"https://t.me/{bot_username}?start={link_code}" if bot_username else f"https://t.me/?start={link_code}"

    return TelegramLinkResponse(
        link_url=link_url,
        code=link_code,
        expires_in_seconds=600
    )
