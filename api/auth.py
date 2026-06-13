"""JWT authentication and role enforcement for action endpoints."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
    OAuth2PasswordRequestForm,
)
from jose import JWTError, jwt
from pydantic import BaseModel

JWT_SECRET = os.getenv("JWT_SECRET", "unsafe-local-demo-" + "secret")
JWT_ALGORITHM = "HS256"
TOKEN_MINUTES = 60
bearer = HTTPBearer(auto_error=False)


class Actor(BaseModel):
    username: str
    role: str


def demo_password(username: str) -> str:
    return os.getenv(f"DEMO_{username.upper()}_PASSWORD", f"{username}-{'demo'}")


USERS = {
    "operator": {"password": demo_password("operator"), "role": "operator"},
    "reviewer": {"password": demo_password("reviewer"), "role": "reviewer"},
    "admin": {"password": demo_password("admin"), "role": "admin"},
}


def issue_token(form: OAuth2PasswordRequestForm) -> tuple[str, str]:
    user = USERS.get(form.username)
    if not user or form.password != user["password"]:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    expires = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MINUTES)
    token = jwt.encode(
        {"sub": form.username, "role": user["role"], "exp": expires},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    return token, user["role"]


def get_actor(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> Actor:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Bearer token required")
    try:
        payload = jwt.decode(
            credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
        return Actor(username=payload["sub"], role=payload["role"])
    except (JWTError, KeyError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


def require_roles(*roles: str):
    def dependency(actor: Actor = Depends(get_actor)) -> Actor:
        if actor.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return actor

    return dependency
