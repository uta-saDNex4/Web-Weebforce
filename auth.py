"""JWT authentication helpers for the Contract Verifier API."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer


# Configure SECRET_KEY in the environment for deployed instances.
SECRET_KEY = os.getenv("SECRET_KEY", "development-only-change-this-secret-key")
ACCESS_TOKEN_EXPIRE_MINUTES = 30
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/login")


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create a signed HS256 JWT access token, expiring after 30 minutes."""
    now = datetime.now(timezone.utc)
    expires_at = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {**data, "iat": int(now.timestamp()), "exp": int(expires_at.timestamp())}
    header = {"alg": "HS256", "typ": "JWT"}
    encoded_header = _b64encode(json.dumps(header, separators=(",", ":")).encode())
    encoded_payload = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = hmac.new(SECRET_KEY.encode(), signing_input, hashlib.sha256).digest()
    return f"{encoded_header}.{encoded_payload}.{_b64encode(signature)}"


def _decode_access_token(token: str) -> dict[str, Any]:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        header = json.loads(_b64decode(encoded_header))
        payload = json.loads(_b64decode(encoded_payload))
        signature = _b64decode(encoded_signature)
    except (ValueError, TypeError, binascii.Error, json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=401, detail="Invalid access token") from None

    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    expected = hmac.new(SECRET_KEY.encode(), signing_input, hashlib.sha256).digest()
    if header.get("alg") != "HS256" or not isinstance(payload, dict) or not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid access token")
    if not isinstance(payload.get("exp"), int) or payload["exp"] <= int(datetime.now(timezone.utc).timestamp()):
        raise HTTPException(status_code=401, detail="Access token has expired")
    return payload


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict[str, Any]:
    """FastAPI dependency validating a Bearer JWT and an active user."""
    payload = _decode_access_token(token)
    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except (KeyError, ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=401, detail="Invalid access token subject") from None

    # Lazy import avoids a circular import while main.py imports this module.
    from main import USERS

    user = USERS.get(user_id)
    if not user or user.get("is_active") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is not active or does not exist",
        )
    return user
