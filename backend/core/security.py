import base64
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from backend.core.database import get_db
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

security_scheme = HTTPBearer(auto_error=False)


# --- AES Encryption for User API Keys (BYOK) ---
def _get_fernet_key(secret: str) -> bytes:
    """Derive a valid 32-byte url-safe base64 key from secret."""
    digest = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)

fernet = Fernet(_get_fernet_key(settings.ENCRYPTION_SECRET))


def encrypt_secret(plain_text: Optional[str]) -> Optional[str]:
    """Encrypt sensitive user API key before saving to DB."""
    if not plain_text:
        return None
    return fernet.encrypt(plain_text.strip().encode()).decode()


def decrypt_secret(cipher_text: Optional[str]) -> Optional[str]:
    """Decrypt user API key for in-memory API execution."""
    if not cipher_text:
        return None
    try:
        return fernet.decrypt(cipher_text.encode()).decode()
    except Exception as e:
        logger.error(f"Error decrypting secret: {e}")
        return None


# --- Password Hashing with bcrypt ---
def hash_password(password: str) -> str:
    """Hash raw password with salt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


# --- JWT Token Generation & Validation ---
def create_access_token(data: Optional[dict] = None, user_id: Optional[str] = None, expires_delta: Optional[timedelta] = None) -> str:
    """Generate signed JWT token."""
    to_encode = data.copy() if data else {}
    if user_id:
        to_encode["sub"] = str(user_id)
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    """Decode and validate JWT token, returning user_id (sub)."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError as e:
        logger.warning(f"JWT decode error: {e}")
        return None


def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
):
    """Dependency to retrieve authenticated user from Bearer JWT token."""
    from backend.models.user import User  # Deferred import to avoid circular dependency

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not auth or not auth.credentials:
        raise credentials_exception

    token = auth.credentials
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except jwt.PyJWTError as e:
        logger.warning(f"JWT verification error: {e}")
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

    return user
