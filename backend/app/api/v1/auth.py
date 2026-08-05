"""
Inscription, connexion, profil.

Deux endpoints de connexion pour une seule logique :
  • `/auth/login` accepte du JSON → utilisé par le frontend.
  • `/auth/token` accepte un formulaire OAuth2 → fait fonctionner le bouton
    « Authorize » de la doc interactive sur /docs, ce qui permet de tester
    toute l'API depuis le navigateur sans coller un token à la main.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserRead,
    UserUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentification"])

# Hash factice servant à comparer même quand l'email est inconnu : sans ça, une
# réponse instantanée révélerait « cet email n'existe pas » par simple mesure
# du temps de réponse.
_DUMMY_HASH = hash_password("timing-attack-mitigation")


def _token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def _authenticate(db, email: str, password: str) -> User:
    user = (
        await db.execute(select(User).where(User.email == email.lower().strip()))
    ).scalar_one_or_none()

    if user is None:
        verify_password(password, _DUMMY_HASH)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
        )
    if not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Compte désactivé."
        )
    return user


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un compte",
)
async def register(payload: RegisterRequest, db: DbSession) -> TokenResponse:
    email = payload.email.lower().strip()

    already = (
        await db.execute(select(User.id).where(User.email == email))
    ).scalar_one_or_none()
    if already:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte existe déjà avec cet email.",
        )

    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
        display_name=payload.display_name.strip() or email.split("@")[0],
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info("Nouveau compte : %s", email)
    return _token_response(user)


@router.post("/login", response_model=TokenResponse, summary="Se connecter (JSON)")
async def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    user = await _authenticate(db, payload.email, payload.password)
    return _token_response(user)


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Se connecter (formulaire OAuth2, pour /docs)",
)
async def token(
    db: DbSession,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> TokenResponse:
    # Dans le standard OAuth2, le champ s'appelle `username` — ici c'est l'email.
    user = await _authenticate(db, form.username, form.password)
    return _token_response(user)


@router.get("/me", response_model=UserRead, summary="Mon profil")
async def read_me(user: CurrentUser) -> User:
    return user


@router.patch("/me", response_model=UserRead, summary="Modifier mon profil")
async def update_me(
    payload: UserUpdate, user: CurrentUser, db: DbSession
) -> User:
    for field_name, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(user, field_name, value)
    await db.commit()
    await db.refresh(user)
    return user
