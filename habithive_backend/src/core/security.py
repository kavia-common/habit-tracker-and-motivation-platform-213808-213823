from __future__ import annotations

import datetime as dt
import uuid

from jose import JWTError, jwt
from passlib.context import CryptContext

from src.core.settings import Settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# PUBLIC_INTERFACE
def hash_password(password: str) -> str:
    """Hash a plain password using bcrypt."""
    return _pwd_context.hash(password)


# PUBLIC_INTERFACE
def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plain password against a stored hash."""
    return _pwd_context.verify(password, password_hash)


# PUBLIC_INTERFACE
def create_access_token(settings: Settings, subject_user_id: uuid.UUID) -> str:
    """Create a JWT access token.

    Args:
        settings: App settings (secret, algorithm, expiry).
        subject_user_id: The user ID to embed as the token subject.

    Returns:
        str: Encoded JWT.
    """
    now = dt.datetime.now(dt.timezone.utc)
    exp = now + dt.timedelta(minutes=settings.access_token_exp_minutes)
    payload = {
        "sub": str(subject_user_id),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


# PUBLIC_INTERFACE
def decode_access_token(settings: Settings, token: str) -> uuid.UUID:
    """Decode and validate a JWT, returning the user id (sub)."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        sub = payload.get("sub")
        if not sub:
            raise ValueError("Token missing subject")
        return uuid.UUID(sub)
    except (JWTError, ValueError) as exc:
        raise ValueError("Invalid or expired token") from exc
