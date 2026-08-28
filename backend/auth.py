"""bcrypt password hashing and signed JWT authentication."""
from __future__ import annotations
import base64, binascii, hashlib, hmac, json, os, uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Annotated
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .database import get_db
from .models import User

SECRET_KEY = os.getenv("SECRET_KEY", "development-only-change-this-secret-key")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except (ValueError, TypeError):
        return False

def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    now = datetime.now(timezone.utc)
    exp = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {**data, "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    header, body = _b64(b'{"alg":"HS256","typ":"JWT"}'), _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(SECRET_KEY.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    return f"{header}.{body}.{_b64(sig)}"

def _decode_access_token(token: str) -> dict[str, Any]:
    try:
        header_text, body_text, sig_text = token.split(".")
        decode = lambda v: base64.urlsafe_b64decode(v + "=" * (-len(v) % 4))
        header, payload, signature = json.loads(decode(header_text)), json.loads(decode(body_text)), decode(sig_text)
        expected = hmac.new(SECRET_KEY.encode(), f"{header_text}.{body_text}".encode(), hashlib.sha256).digest()
        if header.get("alg") != "HS256" or not isinstance(payload, dict) or not hmac.compare_digest(signature, expected): raise ValueError
        if not isinstance(payload.get("exp"), int) or payload["exp"] <= int(datetime.now(timezone.utc).timestamp()): raise HTTPException(401, "Access token has expired")
        return payload
    except HTTPException: raise
    except (ValueError, TypeError, binascii.Error, json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(401, "Invalid access token") from None

def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Annotated[Session, Depends(get_db)]) -> User:
    try: user_id = uuid.UUID(str(_decode_access_token(token)["sub"]))
    except (KeyError, ValueError, TypeError, AttributeError): raise HTTPException(401, "Invalid access token subject") from None
    user = db.get(User, user_id)
    if not user or not user.is_active: raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User is not active or does not exist")
    return user


def check_admin_role(current: Annotated[User, Depends(get_current_user)]) -> User:
    """Allow only administrators to access privileged maintenance endpoints."""
    if current.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="403 Forbidden - Quyền truy cập bị từ chối")
    return current
