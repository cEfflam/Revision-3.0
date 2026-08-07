"""
Bacs à sable SQL et pseudo-code.

SQL : la requête de l'étudiant est RÉELLEMENT exécutée, sur une base SQLite
créée en mémoire pour l'occasion et détruite aussitôt. Rien n'approche du
PostgreSQL de l'application. Son résultat est comparé à celui de la solution,
exécutée dans les mêmes conditions — c'est le résultat qui juge, pas
l'apparence de la requête. Deux formulations différentes qui renvoient la même
chose sont toutes deux justes, et c'est exactement la réalité de SQL.

Pseudo-code : rien à exécuter, par définition. L'IA déroule l'algorithme pas à
pas sur un jeu de valeurs et montre où le résultat diverge — la trace vaut
mieux qu'un verdict.
"""

from __future__ import annotations

import logging
import sqlite3
import time
import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.deps import CurrentUser, DbSession
from app.models.graph import KnowledgeNode
from app.schemas.sandbox import (
    CodeIssue,
    PseudocodeRequest,
    PseudocodeResponse,
    SqlExercise,
    SqlExerciseRequest,
    SqlRunRequest,
    SqlRunResponse,
    TablePreview,
    TraceStep,
)
from app.services.ai import service as ai_service
from app.services.ai.openrouter import AiUnavailable
from app.services.sandbox import sql_runner

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sandbox", tags=["bac à sable"])

# Les exercices vivent en mémoire, jamais en base.
#
# Pourquoi pas en base : un exercice est jeté après résolution, exactement
# comme un quiz. Pourquoi pas côté client : il contient la solution, et
# l'envoyer au navigateur transformerait l'exercice en copier-coller.
#
# L'application est mono-utilisateur et mono-processus : un dictionnaire
# suffit. Les exercices sont perdus au redémarrage, ce qui est sans
# conséquence — on en régénère un.
_EXERCISES: dict[str, dict] = {}
_EXERCISE_TTL_SECONDS = 3 * 3600
_MAX_EXERCISES = 50


def _store(exercise: dict) -> str:
    now = time.time()
    # Purge à l'écriture plutôt qu'en tâche de fond : sans planificateur à
    # maintenir, et le dictionnaire ne peut pas croître indéfiniment.
    for key, value in list(_EXERCISES.items()):
        if now - value["_created"] > _EXERCISE_TTL_SECONDS:
            _EXERCISES.pop(key, None)
    while len(_EXERCISES) >= _MAX_EXERCISES:
        _EXERCISES.pop(next(iter(_EXERCISES)))

    exercise_id = str(uuid.uuid4())
    exercise["_created"] = now
    _EXERCISES[exercise_id] = exercise
    return exercise_id


def _preview_tables(schema_sql: str, seed_sql: str) -> list[TablePreview]:
    """
    Monte la base et renvoie un aperçu de chaque table.

    L'étudiant doit VOIR les données : raisonner sur un schéma sans valeurs
    revient à deviner. C'est aussi ce qui rend le piège découvrable — un NULL
    ne se soupçonne pas, il se constate.
    """
    previews: list[TablePreview] = []
    connection = sqlite3.connect(":memory:")
    try:
        connection.executescript(schema_sql)
        connection.executescript(seed_sql)
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        for table in tables:
            cursor = connection.execute(f'SELECT * FROM "{table}" LIMIT 12')
            columns = [d[0] for d in (cursor.description or [])]
            rows = [[("NULL" if v is None else str(v)) for v in r] for r in cursor]
            total = connection.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0]
            previews.append(
                TablePreview(
                    name=table, columns=columns, rows=rows, row_count=int(total)
                )
            )
    except sqlite3.Error as exc:
        logger.warning("Aperçu des tables impossible : %s", exc)
    finally:
        connection.close()
    return previews


@router.post(
    "/sql/exercise",
    response_model=SqlExercise,
    status_code=status.HTTP_201_CREATED,
    summary="Générer un exercice SQL exécutable",
)
async def create_sql_exercise(
    payload: SqlExerciseRequest, user: CurrentUser, db: DbSession
) -> SqlExercise:
    notion = ""
    if payload.node_id:
        node = await db.get(KnowledgeNode, payload.node_id)
        if node is None or node.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Notion introuvable."
            )
        notion = node.title

    try:
        result = await ai_service.generate_sql_exercise(
            topic=payload.topic, difficulty=payload.difficulty, notion=notion
        )
    except AiUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    schema_sql = str(result.get("schema_sql", "")).strip()
    seed_sql = str(result.get("seed_sql", "")).strip()
    solution = str(result.get("solution", "")).strip()
    if not (schema_sql and solution):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="L'IA n'a pas produit d'exercice exécutable. Réessaie.",
        )

    # Vérification immédiate : un exercice dont la solution ne s'exécute pas
    # est un piège pour l'étudiant, qui chercherait une erreur inexistante.
    expected = sql_runner.run_exercise(
        schema_sql=schema_sql, seed_sql=seed_sql, query=solution
    )
    if not expected.ok:
        logger.warning("Solution générée invalide : %s", expected.error)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "L'exercice généré est invalide (sa propre solution échoue). "
                "Relance la génération."
            ),
        )

    exercise_id = _store(
        {
            "user_id": user.id,
            "schema_sql": schema_sql,
            "seed_sql": seed_sql,
            "solution": solution,
        }
    )

    return SqlExercise(
        exercise_id=exercise_id,
        title=str(result.get("title", "Exercice SQL")),
        question=str(result.get("question", "")),
        hint=str(result.get("hint", "")),
        trap=str(result.get("trap", "")),
        schema_sql=schema_sql,
        tables_preview=_preview_tables(schema_sql, seed_sql),
        model=str(result.get("_model", "")),
        mocked=bool(result.get("_mocked", False)),
    )


@router.post(
    "/sql/run", response_model=SqlRunResponse, summary="Exécuter ma requête"
)
async def run_sql(payload: SqlRunRequest, user: CurrentUser) -> SqlRunResponse:
    exercise = _EXERCISES.get(payload.exercise_id)
    if exercise is None or exercise["user_id"] != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cet exercice a expiré. Génères-en un nouveau.",
        )

    expected = sql_runner.run_exercise(
        schema_sql=exercise["schema_sql"],
        seed_sql=exercise["seed_sql"],
        query=exercise["solution"],
    )

    if payload.give_up:
        return SqlRunResponse(
            correct=False,
            explanation="Voici le résultat attendu et la requête qui le produit.",
            expected_columns=expected.columns,
            expected_rows=[[str(v) for v in row] for row in expected.rows],
            solution=exercise["solution"],
        )

    try:
        student = sql_runner.run_exercise(
            schema_sql=exercise["schema_sql"],
            seed_sql=exercise["seed_sql"],
            query=payload.query,
        )
    except sql_runner.SqlRejected as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    correct, explanation = sql_runner.compare(student, expected)

    return SqlRunResponse(
        correct=correct,
        explanation=explanation,
        columns=student.columns,
        rows=[[("NULL" if v is None else str(v)) for v in row] for row in student.rows],
        error=student.error,
        truncated=student.truncated,
        # Le résultat attendu n'est dévoilé qu'une fois trouvé : le montrer
        # avant supprimerait l'exercice.
        expected_columns=expected.columns if correct else [],
        expected_rows=(
            [[str(v) for v in row] for row in expected.rows] if correct else []
        ),
        solution=exercise["solution"] if correct else "",
    )


@router.post(
    "/pseudocode",
    response_model=PseudocodeResponse,
    summary="Faire dérouler mon algorithme",
)
async def review_pseudocode(
    payload: PseudocodeRequest, user: CurrentUser
) -> PseudocodeResponse:
    """
    Déroule un algorithme pas à pas et signale les erreurs classiques :
    indice de boucle décalé, condition d'arrêt fautive, cas limites oubliés.

    Rien n'est exécuté — du pseudo-code ne s'exécute pas. C'est la TRACE qui
    fait apprendre : voir l'état des variables à chaque tour montre l'erreur
    bien mieux qu'un verdict.
    """
    try:
        result = await ai_service.review_pseudocode(payload.code, payload.intent)
    except AiUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    if not result:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="L'analyse n'a pas pu être exploitée. Réessaie.",
        )

    return PseudocodeResponse(
        correct=bool(result.get("correct", False)),
        trace=[
            TraceStep(
                step=int(t.get("step", i + 1)),
                state=str(t.get("state", "")),
                comment=str(t.get("comment", "")),
            )
            for i, t in enumerate(result.get("trace") or [])
            if isinstance(t, dict)
        ],
        issues=[
            CodeIssue(
                severity=str(i.get("severity", "mineur")),
                line=str(i.get("line", "")),
                problem=str(i.get("problem", "")),
                fix=str(i.get("fix", "")),
            )
            for i in (result.get("issues") or [])
            if isinstance(i, dict)
        ],
        complexity=str(result.get("complexity", "")),
        verdict=str(result.get("verdict", "")),
        model=str(result.get("_model", "")),
        mocked=bool(result.get("_mocked", False)),
    )
