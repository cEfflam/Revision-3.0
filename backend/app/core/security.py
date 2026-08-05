"""
Mots de passe et jetons JWT.

Choix techniques :
  • bcrypt utilisé directement, sans passlib. passlib n'est plus maintenu et
    provoque un warning connu avec bcrypt 4.x. Deux fonctions suffisent.
  • JWT signé en HS256 avec SECRET_KEY. Un token contient l'id utilisateur
    (`sub`) et une date d'expiration (`exp`) — rien de sensible : un JWT est
    signé, pas chiffré, n'importe qui peut lire son contenu.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

# bcrypt ignore tout ce qui dépasse 72 octets et lève une erreur depuis la
# version 4. On tronque donc explicitement, comme le faisait passlib.
_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    payload = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(payload, bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        payload = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
        return bcrypt.checkpw(payload, hashed.encode("utf-8"))
    except (ValueError, TypeError):
        # Hash malformé en base : on refuse, sans faire tomber l'API.
        return False


def create_access_token(
    subject: str | int,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Renvoie le contenu du token, ou None s'il est invalide/expiré."""
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.PyJWTError:
        return None
