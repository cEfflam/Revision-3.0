# ==========================================================================
#  Backend REVISIO — build en 2 étapes (multi-stage).
#
#  Pourquoi 2 étapes ?
#   • L'étape "builder" installe un compilateur C (build-essential) pour les
#     rares paquets sans wheel précompilé.
#   • L'étape "runtime" ne récupère que le venv terminé. Le compilateur, qui
#     ne sert plus à rien, ne finit pas dans l'image finale : ~600 Mo gagnés
#     et une surface d'attaque réduite.
#
#  Python 3.12 (et non 3.13) : c'est la version pour laquelle *tous* les
#  paquets de la stack ML publient des wheels précompilés. On montera plus
#  tard, quand l'écosystème aura suivi.
# ==========================================================================

# ── Étape 1 : construction des dépendances ───────────────────────────────
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt


# ── Étape 2 : image d'exécution ──────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH" \
    HF_HOME=/app/.fastembed_cache

# curl : uniquement pour le HEALTHCHECK ci-dessous.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY . .

RUN mkdir -p storage .fastembed_cache

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
    CMD curl -fsS http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
