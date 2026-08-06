"""
Assemblage des routes de l'API v1.

Chaque module déclare son propre `APIRouter` avec son préfixe ; ce fichier ne
fait que les brancher. Ajouter un domaine = une ligne ici, rien d'autre.
Le préfixe global `/api/v1` est posé dans `main.py` : le jour où une v2
casse la compatibilité, les deux versions cohabiteront côte à côte.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    cards,
    chat,
    dashboard,
    documents,
    health,
    nodes,
    onboarding,
    practice,
    roadmap,
    sessions,
    subjects,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(onboarding.router)
api_router.include_router(dashboard.router)
api_router.include_router(subjects.router)
api_router.include_router(nodes.router)
api_router.include_router(cards.router)
api_router.include_router(documents.router)
api_router.include_router(sessions.router)
api_router.include_router(practice.router)
api_router.include_router(roadmap.router)
api_router.include_router(chat.router)
