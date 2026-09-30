from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import (
    hash_password, verify_password, create_access_token, get_current_user
)
from backend.models.user import User
from backend.models.channel_set import ChannelSet
from backend.schemas.auth import UserRegister, UserLogin, TokenResponse, UserProfile

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    """Register a new user account and initialize their primary channel set."""
    existing_user = db.query(User).filter(User.email == user_in.email.lower()).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this email already exists.")

    # First user registered in the system automatically gets admin privileges
    is_first_user = db.query(User).count() == 0

    new_user = User(
        email=user_in.email.lower(),
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name,
        language=user_in.language or "en",
        is_admin=is_first_user
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Create default channel set
    default_set = ChannelSet(
        user_id=new_user.id,
        name="Primary",
        description="My primary monitored competitor set",
        schedule_time="12:00",
        schedule_timezone="UTC",
        schedule_enabled=True
    )
    db.add(default_set)
    db.commit()
    db.refresh(default_set)

    new_user.active_set_id = default_set.id
    db.commit()

    token = create_access_token({"sub": new_user.id, "email": new_user.email})
    return TokenResponse(
        access_token=token,
        user_id=new_user.id,
        email=new_user.email,
        language=new_user.language,
        active_set_id=new_user.active_set_id,
        is_admin=new_user.is_admin
    )


@router.post("/login", response_model=TokenResponse)
def login(login_in: UserLogin, db: Session = Depends(get_db)):
    """Authenticate with email and password and receive JWT session token."""
    user = db.query(User).filter(User.email == login_in.email.lower()).first()
    if not user or not verify_password(login_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )

    if not user.is_active:
        raise HTTPException(status_code=400, detail="User account is deactivated.")

    token = create_access_token({"sub": user.id, "email": user.email})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        language=user.language,
        active_set_id=user.active_set_id,
        is_admin=user.is_admin
    )


@router.get("/me", response_model=UserProfile)
def get_profile(current_user: User = Depends(get_current_user)):
    """Retrieve profile and API key status for authenticated user."""
    return UserProfile(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        language=current_user.language or "en",
        active_set_id=current_user.active_set_id,
        is_active=current_user.is_active,
        is_admin=current_user.is_admin,
        has_youtube_key=bool(current_user.youtube_api_key_encrypted),
        has_gemini_key=bool(current_user.gemini_api_key_encrypted),
        youtube_api_key_valid=bool(current_user.youtube_api_key_valid),
        gemini_api_key_valid=bool(current_user.gemini_api_key_valid),
        telegram_chat_id=current_user.telegram_chat_id,
        created_at=current_user.created_at
    )


from pydantic import BaseModel


class LanguageUpdateRequest(BaseModel):
    language: str


@router.put("/me/language")
@router.patch("/me/language")
def update_language(
    payload: Optional[LanguageUpdateRequest] = None,
    language: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update preferred interface and report language (ru, en, de, fi, ka)."""
    raw_lang = (payload.language if payload else language) or ""
    lang_clean = raw_lang.strip().lower()
    if lang_clean not in ("ru", "en", "de", "fi", "ka"):
        raise HTTPException(status_code=400, detail="Supported languages: ru, en, de, fi, ka")

    current_user.language = lang_clean
    db.commit()
    return {"status": "SUCCESS", "language": lang_clean}

