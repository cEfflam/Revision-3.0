"""
Moteurs conversationnels.

Un seul endpoint pour tous les moteurs : c'est le champ `task` qui choisit le
prompt système, donc le comportement. `math_hint` refusera de donner la réponse,
`explain_code` structurera son analyse en quatre points, `cejm_case` appliquera
la méthode juridique. Toute la pédagogie est dans `services/ai/prompts.py` —
aucune logique de matière n'est codée en dur ici.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.core.deps import CurrentUser, DbSession
from app.models.graph import KnowledgeNode
from app.schemas.ai import (
    ChatRequest,
    ChatResponse,
    SourceRead,
    WritingAnalysisRequest,
    WritingAnalysisResponse,
    WritingIssue,
)
from app.services.ai import service as ai_service
from app.services.ai.openrouter import AiUnavailable, ChatMessage, get_ai_client
from app.services.ai.router import AiTask, reasoning_enabled, role_for

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["moteurs IA"])

# Moteurs pour lesquels chercher dans les documents de cours n'apporte rien.
NO_RAG_TASKS = {AiTask.english_chat, AiTask.math_hint}


@router.post("", response_model=ChatResponse, summary="Dialoguer avec un moteur")
async def chat(
    payload: ChatRequest, user: CurrentUser, db: DbSession
) -> ChatResponse:
    subject = payload.subject.value if payload.subject else None

    # Un node_id fourni contextualise la question : la matière du nœud sert à
    # cibler la recherche documentaire.
    if payload.node_id:
        node = await db.get(KnowledgeNode, payload.node_id)
        if node is None or node.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Notion introuvable."
            )
        subject = subject or node.subject

    use_rag = (
        payload.use_rag
        if payload.use_rag is not None
        else payload.task not in NO_RAG_TASKS
    )

    try:
        result = await ai_service.ask(
            db,
            user,
            payload.message,
            task=payload.task,
            subject=subject,
            use_rag=use_rag,
            # Déclenche le premier étage : si la notion a une synthèse, elle
            # est fournie avant les fragments bruts.
            node_id=payload.node_id,
            history=[
                ChatMessage(role=m.role, content=m.content) for m in payload.history
            ],
        )
    except AiUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    return ChatResponse(
        answer=result.answer,
        # `model_validate` et non `vars()` : les dataclasses déclarées avec
        # slots=True n'ont pas de __dict__, et vars() lève une TypeError dès
        # qu'une source remonte réellement.
        sources=[SourceRead.model_validate(s) for s in result.sources],
        model=result.model,
        tier=role_for(payload.task).value,
        mocked=result.mocked,
        latency_ms=result.latency_ms,
        tokens=result.tokens,
    )


@router.post(
    "/writing-analysis",
    response_model=WritingAnalysisResponse,
    summary="Auditer un écrit de CGE",
)
async def analyse_writing(
    payload: WritingAnalysisRequest, user: CurrentUser
) -> WritingAnalysisResponse:
    """
    Audit fin d'une synthèse ou d'une écriture personnelle.

    Ne renvoie pas qu'une note : une liste de problèmes localisés, chacun avec
    un extrait exact du texte pour que l'interface puisse le surligner. Une note
    seule n'apprend rien ; « ce paragraphe répète l'idée du premier » se
    corrige.
    """
    try:
        payload_dict = await ai_service.analyse_writing(payload.text)
    except AiUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    issues: list[WritingIssue] = []
    for raw in payload_dict.get("issues", []) or []:
        if not isinstance(raw, dict):
            continue
        issues.append(
            WritingIssue(
                type=str(raw.get("type", "other")),
                severity=str(raw.get("severity", "info")),
                label=str(raw.get("label", "Point à revoir")),
                # L'extrait n'est conservé que s'il figure réellement dans le
                # texte : le frontend surligne par recherche exacte, un extrait
                # reformulé par le modèle ne serait jamais trouvé.
                quote=(
                    str(raw.get("quote", ""))
                    if str(raw.get("quote", "")) in payload.text
                    else ""
                ),
                detail=str(raw.get("detail", "")),
                suggestion=str(raw.get("suggestion", "")),
            )
        )

    score = payload_dict.get("score")
    mocked = get_ai_client().is_mocked
    return WritingAnalysisResponse(
        score=float(score) if isinstance(score, (int, float)) else None,
        issues=issues,
        strengths=[str(s) for s in (payload_dict.get("strengths") or [])],
        next_step=str(payload_dict.get("next_step", "")),
        model="mock" if mocked else "openrouter",
        mocked=mocked,
    )


@router.get("/engines", summary="Moteurs disponibles")
async def list_engines() -> list[dict[str, str]]:
    """Alimente le sélecteur de moteur dans l'interface."""
    labels = {
        AiTask.chat: "Question sur mes cours",
        AiTask.explain_code: "Analyse de code",
        AiTask.sql_review: "Correction SQL",
        AiTask.math_hint: "Maths (guidage socratique)",
        AiTask.cejm_case: "Cas pratique CEJM",
        AiTask.cge_analysis: "Audit d'écrit (CGE)",
        AiTask.english_chat: "Conversation en anglais",
        AiTask.error_analysis: "Analyse de mes erreurs",
    }
    return [
        {
            "task": task.value,
            "label": label,
            # « language » = Qwen (français, rédaction, JSON) ;
            # « reasoning » = DeepSeek (maths, algo, code).
            "tier": role_for(task).value,
            "reasoning": str(reasoning_enabled(task)).lower(),
            "uses_documents": str(task not in NO_RAG_TASKS).lower(),
        }
        for task, label in labels.items()
    ]
