"""
Tests du garde-fou sur les réponses JSON des modèles.

Ces cas ne sont pas théoriques : en production, le modèle a renvoyé un objet
parfaitement valide contenant `title`, `context` et `total_points`… mais sans
la clé `questions`. Le sujet était donc syntaxiquement bon et totalement
inutilisable, et l'utilisateur voyait une erreur sans explication.
"""

from __future__ import annotations

import json

from app.services.ai.openrouter import _is_usable_json, parse_json_response
from app.services.ai.router import AiTask, required_json_key


def test_required_keys_are_declared_for_collection_tasks() -> None:
    assert required_json_key(AiTask.exam_generate) == "questions"
    assert required_json_key(AiTask.flashcards) == "cards"
    assert required_json_key(AiTask.roadmap) == "steps"
    # Une analyse sans problème détecté est un résultat valide : aucune clé
    # n'est exigée, sinon on rejetterait une copie parfaite.
    assert required_json_key(AiTask.cge_analysis) is None


def test_missing_required_key_is_rejected() -> None:
    payload = json.dumps(
        {"title": "Cas pratique", "context": "…", "total_points": 20}
    )
    assert _is_usable_json(payload, "questions") is False


def test_empty_required_key_is_rejected() -> None:
    assert _is_usable_json(json.dumps({"questions": []}), "questions") is False


def test_present_required_key_is_accepted() -> None:
    payload = json.dumps({"questions": [{"number": 1, "text": "…"}]})
    assert _is_usable_json(payload, "questions") is True


def test_no_required_key_accepts_any_valid_object() -> None:
    assert _is_usable_json(json.dumps({"score": 12}), None) is True


def test_malformed_json_is_rejected() -> None:
    assert _is_usable_json("désolé, je ne peux pas", "questions") is False
    assert _is_usable_json("", None) is False


def test_json_is_extracted_from_a_markdown_fence() -> None:
    """Les modèles encadrent volontiers leur JSON d'un bloc de code."""
    wrapped = 'Voici le résultat :\n```json\n{"cards": [{"front": "a"}]}\n```'
    assert parse_json_response(wrapped) == {"cards": [{"front": "a"}]}
    assert _is_usable_json(wrapped, "cards") is True


def test_json_is_extracted_from_surrounding_prose() -> None:
    noisy = 'Bien sûr ! {"steps": [{"title": "Étape 1"}]} J\'espère que ça aide.'
    assert _is_usable_json(noisy, "steps") is True
