"""
Exécution réelle de requêtes SQL, en bac à sable.

POURQUOI SQLITE EN MÉMOIRE
──────────────────────────
Exécuter la requête d'un étudiant sur le PostgreSQL de l'application serait
irresponsable : un DROP TABLE mal placé, une requête qui bloque une table, ou
simplement une erreur qui pollue les logs de production.

SQLite en mémoire résout tout d'un coup :
  • base créée et détruite à chaque requête, rien ne survit ;
  • aucune connexion réseau, aucun fichier sur disque ;
  • présent dans la bibliothèque standard, zéro dépendance ;
  • un timeout suffit à borner une requête qui part en boucle.

La contrepartie est réelle : SQLite n'est pas PostgreSQL. Pas de RIGHT JOIN,
pas de FULL OUTER JOIN, pas de types stricts. Le prompt de génération en tient
compte, et l'écart est signalé à l'étudiant plutôt que caché.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field

#: Au-delà, on considère que la requête boucle. Une requête d'exercice sur
#: douze lignes n'a aucune raison de dépasser la seconde.
TIMEOUT_SECONDS = 3.0
#: Garde-fou contre une jointure croisée involontaire qui remplirait la RAM.
MAX_ROWS = 500
#: Nombre maximal d'instructions VM avant interruption (protection anti-boucle).
MAX_VM_STEPS = 2_000_000

#: Mots-clés refusés dans la requête de l'étudiant. La base est jetable, mais
#: laisser passer un DROP donnerait un message d'erreur incompréhensible au
#: lieu d'un rappel pédagogique : un exercice de lecture se résout en SELECT.
FORBIDDEN = re.compile(
    r"\b(drop|delete|update|insert|alter|create|replace|attach|pragma|vacuum)\b",
    flags=re.IGNORECASE,
)


class SqlRejected(ValueError):
    """La requête est refusée avant même d'être exécutée."""


@dataclass(slots=True)
class QueryResult:
    columns: list[str] = field(default_factory=list)
    rows: list[list[object]] = field(default_factory=list)
    error: str = ""
    truncated: bool = False

    @property
    def ok(self) -> bool:
        return not self.error

    def signature(self) -> tuple:
        """
        Empreinte comparable de deux résultats.

        L'ordre des lignes n'est PAS pris en compte, sauf si la requête impose
        un ORDER BY — comparer des ensembles évite de refuser une bonne réponse
        pour une raison qui n'en est pas une. Les valeurs sont converties en
        texte : SQLite peut renvoyer 1 là où la solution renvoie 1.0.
        """
        return tuple(sorted(tuple(str(v) for v in row) for row in self.rows))


def _new_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", timeout=TIMEOUT_SECONDS)
    # Interrompt toute requête qui dépasse le budget d'instructions : c'est ce
    # qui protège d'une jointure explosive ou d'un CTE récursif sans sortie.
    steps = 0

    def guard() -> int:
        nonlocal steps
        steps += 1
        return 1 if steps > MAX_VM_STEPS else 0

    connection.set_progress_handler(guard, 1000)
    return connection


def _execute_script(connection: sqlite3.Connection, script: str) -> None:
    if script.strip():
        connection.executescript(script)


def run_exercise(
    *, schema_sql: str, seed_sql: str, query: str
) -> QueryResult:
    """
    Monte la base, exécute la requête de l'étudiant, rend le résultat.

    La base entière vit et meurt dans cet appel.
    """
    query = (query or "").strip().rstrip(";")
    if not query:
        raise SqlRejected("Écris une requête avant de l'exécuter.")

    if FORBIDDEN.search(query):
        raise SqlRejected(
            "Seules les requêtes de lecture (SELECT) sont acceptées ici. "
            "L'exercice porte sur l'interrogation des données, pas sur leur "
            "modification."
        )
    # Une seule instruction : deux requêtes enchaînées rendraient la
    # comparaison avec la solution ambiguë.
    if ";" in query:
        raise SqlRejected("Une seule requête à la fois, sans point-virgule.")

    connection = _new_connection()
    try:
        _execute_script(connection, schema_sql)
        _execute_script(connection, seed_sql)

        cursor = connection.execute(query)
        columns = [d[0] for d in (cursor.description or [])]
        rows = cursor.fetchmany(MAX_ROWS + 1)
        truncated = len(rows) > MAX_ROWS
        return QueryResult(
            columns=columns,
            rows=[list(r) for r in rows[:MAX_ROWS]],
            truncated=truncated,
        )
    except sqlite3.Error as exc:
        # L'erreur SQLite est rendue telle quelle : c'est elle qui apprend.
        return QueryResult(error=str(exc))
    finally:
        connection.close()


def compare(student: QueryResult, expected: QueryResult) -> tuple[bool, str]:
    """
    Compare le résultat de l'étudiant à celui attendu.

    Renvoie (correct, explication). L'explication vise à faire comprendre
    l'écart, pas à juger : « 3 lignes au lieu de 5 » oriente vers la jointure
    ou le filtre fautif.
    """
    if not student.ok:
        return False, f"La requête n'a pas pu s'exécuter : {student.error}"
    if not expected.ok:
        return False, "L'exercice est invalide : la solution ne s'exécute pas."

    if student.signature() == expected.signature():
        return True, "Résultat exact."

    if len(student.rows) != len(expected.rows):
        return False, (
            f"{len(student.rows)} ligne(s) renvoyée(s) au lieu de "
            f"{len(expected.rows)}. Regarde du côté des jointures et des "
            "conditions de filtrage."
        )
    if len(student.columns) != len(expected.columns):
        return False, (
            f"{len(student.columns)} colonne(s) au lieu de "
            f"{len(expected.columns)}. Vérifie ce que tu sélectionnes."
        )
    return False, (
        "Le bon nombre de lignes, mais des valeurs différentes. L'erreur est "
        "probablement dans un calcul, un regroupement, ou une colonne choisie."
    )
