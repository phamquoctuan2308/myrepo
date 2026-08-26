from datetime import UTC, datetime, timedelta
from uuid import uuid4

import bcrypt
import jwt

from src.config import get_settings

settings = get_settings()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    # Access tokens intentionally keep the project's original {sub, exp} shape, while a
    # short-lived WebSocket ticket can never be reused against REST endpoints.
    if payload.get("token_type", "access") != "access":
        raise jwt.InvalidTokenError("Invalid token type")
    return payload["sub"]


def create_websocket_ticket(user_id: str) -> str:
    """Mint a short-lived ticket so the long-lived bearer token never appears in a WS URL."""
    payload = {
        "sub": user_id,
        "exp": datetime.now(UTC) + timedelta(seconds=60),
        "token_type": "websocket",
        "jti": uuid4().hex,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_websocket_ticket(ticket: str) -> str:
    payload = jwt.decode(ticket, settings.secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("token_type") != "websocket" or not payload.get("jti"):
        raise jwt.InvalidTokenError("Invalid WebSocket ticket")
    return payload["sub"]
