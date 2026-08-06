"""
Point d'entrée de l'application FastAPI.

`lifespan` encadre la vie du process : ce qui précède le `yield` s'exécute au
démarrage (logs, dossier de stockage, compte de démonstration), ce qui le suit
s'exécute à l'arrêt (fermeture propre des clients HTTP et Qdrant). C'est le
remplaçant moderne des vieux événements `startup`/`shutdown`.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app import __version__
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)


async def _seed_demo_user() -> None:
    """
    Crée un compte de démonstration complet (objectif, graphe, cartes) pour
    pouvoir tester l'application dès le premier démarrage, sans passer par
    l'inscription. Dev uniquement, et idempotent : si le compte existe, on ne
    touche à rien.
    """
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.core.security import hash_password
    from app.models.graph import KnowledgeNode
    from app.models.learning import Card
    from app.models.user import Goal, SelfAssessment, User
    from app.services.seed import seed_curriculum

    async with SessionLocal() as db:
        existing = (
            await db.execute(
                select(User.id).where(User.email == settings.DEMO_USER_EMAIL)
            )
        ).scalar_one_or_none()
        if existing:
            return

        user = User(
            email=settings.DEMO_USER_EMAIL,
            hashed_password=hash_password(settings.DEMO_USER_PASSWORD),
            display_name="Démo",
            daily_minutes=45,
            onboarding_completed=True,
        )
        db.add(user)
        await db.flush()

        # L'épreuve du BTS, en mai de l'année scolaire en cours ou suivante.
        today = date.today()
        exam_year = today.year + 1 if today.month >= 6 else today.year
        db.add(
            Goal(
                user_id=user.id,
                title="Réussir le BTS SIO (SLAM)",
                kind="diploma",
                description="Objectif : mention, et des bases solides pour la suite.",
                target_date=date(exam_year, 5, 15),
                daily_minutes=45,
                is_primary=True,
            )
        )

        levels = {
            "sql": 45, "dev": 50, "network": 30, "security": 25,
            "math": 40, "cejm": 30, "cge": 35, "english": 55,
        }
        for subject, level in levels.items():
            db.add(SelfAssessment(user_id=user.id, subject=subject, level=level))

        await seed_curriculum(db, user, assessments=levels)

        # Quelques cartes immédiatement dues : la file de révision n'est pas
        # vide à la première ouverture.
        nodes_by_slug = {
            n.slug: n
            for n in (
                await db.execute(
                    select(KnowledgeNode).where(
                        KnowledgeNode.user_id == user.id,
                        KnowledgeNode.slug.in_(
                            ["sql-select", "sql-cle-etrangere", "net-osi", "en-vocab-it"]
                        ),
                    )
                )
            ).scalars()
        }
        samples = [
            ("sql-select", "Quelle clause SQL filtre les lignes AVANT agrégation ?",
             "WHERE (HAVING filtre après le GROUP BY).", ""),
            ("sql-select", "Que renvoie SELECT DISTINCT ville FROM clients ?",
             "La liste des villes sans doublons.", ""),
            ("sql-cle-etrangere", "À quoi sert une clé étrangère ?",
             "À garantir qu'une valeur référence bien une ligne existante d'une "
             "autre table (intégrité référentielle).",
             "Pense au lien commande → client."),
            ("sql-cle-etrangere", "Que se passe-t-il avec ON DELETE CASCADE ?",
             "La suppression du parent supprime automatiquement les lignes "
             "enfants qui le référencent.", ""),
            ("net-osi", "Quelle couche OSI gère l'adressage IP ?",
             "La couche 3 — réseau.", "Physique, liaison, puis…"),
            ("net-osi", "TCP appartient à quelle couche OSI ?",
             "La couche 4 — transport.", ""),
            ("en-vocab-it", "Traduire : « déployer une application »",
             "To deploy an application.", ""),
            ("en-vocab-it", "Que signifie « to troubleshoot » ?",
             "Diagnostiquer et résoudre un problème.", ""),
        ]
        for slug, front, back, hint in samples:
            node = nodes_by_slug.get(slug)
            db.add(
                Card(
                    user_id=user.id,
                    node_id=node.id if node else None,
                    front=front,
                    back=back,
                    hint=hint,
                )
            )

        await db.commit()
        logger.info(
            "Compte de démonstration prêt : %s / %s",
            settings.DEMO_USER_EMAIL,
            settings.DEMO_USER_PASSWORD,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(
        "%s v%s — env=%s, AI_MOCK=%s",
        settings.APP_NAME, __version__, settings.ENVIRONMENT, settings.AI_MOCK,
    )

    if settings.SEED_DEMO_USER and not settings.is_production:
        try:
            await _seed_demo_user()
        except Exception:
            # Un seed raté (base pas encore migrée, par ex.) ne doit pas
            # empêcher l'API de démarrer.
            logger.exception("Échec du seed du compte de démonstration.")

    yield

    from app.services.ai.openrouter import get_ai_client
    from app.services.rag.qdrant import get_vector_store

    await get_ai_client().close()
    await get_vector_store().close()


app = FastAPI(
    title=f"{settings.APP_NAME} API",
    version=__version__,
    lifespan=lifespan,
    # La doc interactive reste accessible en dev ; en production on la coupe,
    # inutile d'exposer la carte complète de l'API.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
)

# En développement, tout localhost est accepté quel que soit le port. Next.js
# bascule sur un port libre quand 3000 est pris, et une liste blanche figée est
# alors systématiquement prise en défaut : le navigateur reçoit un « Failed to
# fetch » que rien ne distingue d'un backend éteint.
# En production, seules les origines déclarées passent.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=(
        None if settings.is_production else r"http://(localhost|127\.0\.0\.1):\d+"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs" if not settings.is_production else "/api/v1/health")
