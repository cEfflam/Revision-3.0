"""Schémas des bacs à sable SQL et pseudo-code, et de la technique Feynman."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import Subject


# ═════════════════════════════════════════════════════════════════════════
#  Bac à sable SQL
# ═════════════════════════════════════════════════════════════════════════
class SqlExerciseRequest(BaseModel):
    node_id: int | None = None
    topic: str = Field(default="", max_length=200)
    difficulty: int = Field(default=2, ge=1, le=5)


class TablePreview(BaseModel):
    """Aperçu d'une table, pour que l'étudiant voie les données réelles."""

    name: str
    columns: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    row_count: int = 0


class SqlExercise(BaseModel):
    # Identifiant du sujet conservé côté serveur. La solution n'est JAMAIS
    # envoyée au navigateur : elle ferait de l'exercice un copier-coller.
    exercise_id: str
    title: str
    question: str
    hint: str = ""
    trap: str = ""
    #: Le schéma est montré : lire une structure fait partie de l'exercice.
    schema_sql: str = ""
    tables_preview: list[TablePreview] = Field(default_factory=list)
    model: str = ""
    mocked: bool = False


class SqlRunRequest(BaseModel):
    exercise_id: str
    query: str = Field(min_length=1, max_length=4000)
    #: Abandon : révèle le résultat attendu et la solution.
    give_up: bool = False


class SqlRunResponse(BaseModel):
    correct: bool = False
    explanation: str = ""
    columns: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    error: str = ""
    truncated: bool = False
    # Le résultat attendu n'apparaît qu'une fois la réponse juste, ou après
    # abandon explicite : le montrer trop tôt supprime l'exercice.
    expected_columns: list[str] = Field(default_factory=list)
    expected_rows: list[list[str]] = Field(default_factory=list)
    solution: str = ""


# ═════════════════════════════════════════════════════════════════════════
#  Bac à sable pseudo-code
# ═════════════════════════════════════════════════════════════════════════
class PseudocodeRequest(BaseModel):
    code: str = Field(min_length=10, max_length=8000)
    intent: str = Field(default="", max_length=500)


class TraceStep(BaseModel):
    step: int
    state: str = ""
    comment: str = ""


class CodeIssue(BaseModel):
    severity: str = "mineur"
    line: str = ""
    problem: str = ""
    fix: str = ""


class PseudocodeResponse(BaseModel):
    correct: bool = False
    trace: list[TraceStep] = Field(default_factory=list)
    issues: list[CodeIssue] = Field(default_factory=list)
    complexity: str = ""
    verdict: str = ""
    model: str = ""
    mocked: bool = False


# ═════════════════════════════════════════════════════════════════════════
#  Technique Feynman
# ═════════════════════════════════════════════════════════════════════════
class FeynmanRequest(BaseModel):
    explanation: str = Field(min_length=20, max_length=8000)


class FeynmanPoint(BaseModel):
    #: "acquis" | "flou" | "manquant" | "errone"
    status: str = "flou"
    label: str = ""
    detail: str = ""
    #: Le passage du cours à relire — c'est l'étape 4 de la méthode.
    course_extract: str = ""
    #: Question qui pousse à combler la lacune soi-même, sans donner la réponse.
    question: str = ""


class FeynmanResponse(BaseModel):
    node_id: int
    node_title: str
    #: 0 à 100 : capacité à dire les choses simplement, sans trou.
    fluency: int = 0
    verdict: str = ""
    points: list[FeynmanPoint] = Field(default_factory=list)
    next_action: str = ""
    #: Effet sur la maîtrise : expliquer clairement EST une preuve de maîtrise.
    mastery_delta: float = 0.0
    mastery_after: float = 0.0
    model: str = ""
    mocked: bool = False


class SandboxSubject(BaseModel):
    subject: Subject
    label: str
