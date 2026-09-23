from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password at least 6 characters")
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    language: str
    active_set_id: Optional[str] = None


class UserProfile(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    language: str
    active_set_id: Optional[str] = None
    
    has_youtube_key: bool
    has_gemini_key: bool
    youtube_api_key_valid: bool
    gemini_api_key_valid: bool
    
    telegram_chat_id: Optional[str] = None
    created_at: datetime


class UserKeysUpdate(BaseModel):
    youtube_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None


class VerifyKeyRequest(BaseModel):
    key_type: str = Field(..., pattern="^(youtube|gemini)$")
    api_key: Optional[str] = None  # If not provided, verifies currently saved key


class VerifyKeyResponse(BaseModel):
    key_type: str
    is_valid: bool
    message: str
    quota_available: bool = False


class TelegramLinkResponse(BaseModel):
    link_url: str
    code: str
    expires_in_seconds: int = 600
