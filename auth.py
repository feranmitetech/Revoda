"""
Revoda — Partner Authentication
JWT-based tokens for CSO partners, observer groups, and admin.
"""

import os
import bcrypt
from datetime import datetime, timezone, timedelta
from typing import Optional
from jose import jwt, JWTError


SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-secret-in-production")
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 90


def verify_partner_token(token: Optional[str]) -> Optional[dict]:
    """Verify a JWT partner token. Returns partner payload or None."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "partner":
            return None
        return payload
    except JWTError:
        return None


def create_partner_token(org_name: str, permissions: dict) -> str:
    """Create a JWT for a partner organisation."""
    expire = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)
    payload = {
        "type": "partner",
        "org_name": org_name,
        "permissions": permissions,
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def hash_api_token(token: str) -> str:
    """Store bcrypt hash of raw API token in DB."""
    return bcrypt.hashpw(token.encode(), bcrypt.gensalt()).decode()


def verify_api_token(raw_token: str, hashed: str) -> bool:
    return bcrypt.checkpw(raw_token.encode(), hashed.encode())
