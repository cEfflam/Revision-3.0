"""
Dépendances partagées par les endpoints.

`CurrentUser` est le type à utiliser partout où une route doit être protégée :

    @router.get("/moi")
    async def moi(user: CurrentUser):
        return user

FastAPI se charge d'extraire l'en-tête Authorization, de valider le JWT, de
charger l'utilisateur en base, et de renvoyer 401 si quoi que ce soit cloche.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

# tokenUrl sert au bouton "Authorize" de la doc Swagger (/docs).
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/token",
    auto_error=False,
)

DbSession = Annotated[AsyncSession, Depends(get_db)]

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Identifiants invalides ou session expirée.",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    db: DbSession,
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
) -> User:
    if not token:
        raise _CREDENTIALS_ERROR

    payload = decode_access_token(token)
    if not payload or payload.get("type") != "access":
        raise _CREDENTIALS_ERROR

    subject = payload.get("sub")
    if not subject:
        raise _CREDENTIALS_ERROR

    user = await db.get(User, int(subject)) if subject.isdigit() else None
    if user is None or not user.is_active:
        raise _CREDENTIALS_ERROR

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
