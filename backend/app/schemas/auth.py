"""Schémas d'authentification et de profil."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    # 8 caractères minimum, 128 maximum. La borne haute n'est pas décorative :
    # sans elle, on accepterait un « mot de passe » de 10 Mo à hacher.
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    display_name: str
    daily_minutes: int
    onboarding_completed: bool
    streak_current: int
    streak_best: int
    last_active_day: date | None = None


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    daily_minutes: int | None = Field(default=None, ge=5, le=600)
    timezone: str | None = Field(default=None, max_length=64)
