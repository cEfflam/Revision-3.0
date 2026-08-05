"""Petites fonctions utilitaires transverses."""

from __future__ import annotations

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(value: str, *, max_length: int = 160) -> str:
    """
    « Jointures SQL (INNER JOIN) » → « jointures-sql-inner-join ».

    Les accents sont décomposés puis les diacritiques supprimés : « é » devient
    « e » plutôt que de disparaître, ce qui garderait « rvision » — illisible.
    """
    normalised = unicodedata.normalize("NFKD", value)
    ascii_only = normalised.encode("ascii", "ignore").decode("ascii")
    slug = _NON_ALNUM.sub("-", ascii_only.lower()).strip("-")
    return slug[:max_length] or "notion"


def truncate(value: str, limit: int, suffix: str = "…") -> str:
    value = value.strip()
    return value if len(value) <= limit else value[: limit - len(suffix)] + suffix
