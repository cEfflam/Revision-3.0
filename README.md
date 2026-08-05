# 🧠 REVISIO 3.0

> **Un OS d'apprentissage personnel** — graphe de connaissances, répétition
> espacée (SRS), RAG vectoriel et coach IA. Conçu pour le BTS SIO aujourd'hui,
> pour tout le reste ensuite.

![Next.js](https://img.shields.io/badge/Next.js-15-000000?logo=nextdotjs&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6?logo=typescript&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Qdrant](https://img.shields.io/badge/Qdrant-1.12-DC244C?logo=qdrant&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

📄 [Cahier des charges](docs/SPECIFICATIONS.md) · 🔀 [Workflow Git & conventions](docs/GIT-WORKFLOW.md)

---

## 🚀 Démarrage rapide

**Prérequis** : Docker Desktop (démarré) et Node.js 22+. Python n'est *pas*
nécessaire sur ta machine : le backend tourne dans Docker.

```bash
# 1. Configuration (le .env n'est jamais commité)
cp .env.example .env

# 2. Démarrer PostgreSQL + Qdrant + backend
docker compose up -d --build

# 3. Frontend en mode développement (plus rapide en natif que dans Docker)
cd frontend && npm install && npm run dev
```

| Service            | URL                              |
| ------------------ | -------------------------------- |
| Application        | http://localhost:3000            |
| API + doc Swagger  | http://localhost:8000/docs       |
| Dashboard Qdrant   | http://localhost:6333/dashboard  |
| PostgreSQL (hôte)  | localhost:5433                   |

**Compte de démo** (créé automatiquement en dev) : `demo@revisio.app` / `revisio123`
— objectif, graphe BTS SIO et cartes de révision déjà en place.

> 💡 **L'IA démarre en mode simulé** (`AI_MOCK=true`) : aucune clé API, aucun
> coût, réponses factices mais déterministes — tout le pipeline est testable.
> Pour de vraies réponses : `AI_MOCK=false` + `OPENROUTER_API_KEY=…` dans le
> `.env`, puis `docker compose restart backend`.

---

## 🧰 Stack technique

### Frontend

| Techno | Version | Rôle |
| --- | --- | --- |
| **Next.js** | 15 (App Router) | Framework React, routage par fichiers, build `standalone` |
| **React** | 19 | Bibliothèque UI |
| **TypeScript** | 5.7 | Typage strict, contrats d'API vérifiés à la compilation |
| **Tailwind CSS** | 3.4 | Design system utilitaire (soft UI indigo) |
| **Framer Motion** | 11 | Transitions des cartes de révision |
| **Lucide React** | — | Jeu d'icônes |
| **clsx + tailwind-merge** | — | Composition de classes sans conflit |

### Backend

| Techno | Version | Rôle |
| --- | --- | --- |
| **Python** | 3.12 | Uniquement dans Docker — rien à installer sur ta machine |
| **FastAPI** | 0.115 | API REST asynchrone + doc OpenAPI générée |
| **Pydantic** | v2 | Validation des entrées/sorties, configuration typée |
| **SQLAlchemy** | 2.0 (async) | ORM, requêtes typées |
| **Alembic** | 1.14 | Migrations de schéma versionnées |
| **asyncpg** | 0.30 | Driver PostgreSQL asynchrone |
| **PyJWT + bcrypt** | — | Authentification par jeton, hachage des mots de passe |
| **httpx** | 0.28 | Client HTTP asynchrone (OpenRouter) |
| **pypdf + python-docx** | — | Extraction de texte PDF / Word |
| **pytest + ruff** | — | Tests et linting |

### Données & IA

| Techno | Rôle |
| --- | --- |
| **PostgreSQL 16** | Source de vérité : utilisateurs, graphe, cartes SRS, historique, statistiques |
| **Qdrant 1.12** | Base vectorielle : recherche sémantique sur les documents (RAG) |
| **fastembed** | Embeddings **en local**, gratuits, sans clé API (`paraphrase-multilingual-MiniLM-L12-v2`, 384 dim) |
| **OpenRouter** | Passerelle multi-modèles (DeepSeek, Qwen, Gemini…) avec routage par coût |

### Infrastructure

| Techno | Rôle |
| --- | --- |
| **Docker + Compose** | Orchestration des 4 services, builds multi-étapes |
| **Nginx** *(prévu)* | Reverse proxy + HTTPS Let's Encrypt |
| **GitHub Actions** *(prévu)* | CI : lint, tests, build des images |

---

## 🏛 Architecture

```
 Next.js 15 (frontend)  ──REST──►  FastAPI (backend)
                                       │
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                  ▼
               PostgreSQL           Qdrant           OpenRouter
            users, graphe,      vecteurs (RAG)      DeepSeek/Qwen…
            cartes SRS, stats                       (via AI Router)
```

Trois moteurs font la valeur du produit :

| Moteur | Fichier | Rôle |
| --- | --- | --- |
| **SRS (SM-2)** | `backend/app/services/srs/sm2.py` | Programme chaque carte juste avant l'oubli. Fonctions pures, testées, remplaçables par FSRS sans perte de données (`ReviewLog` garde tout l'historique). |
| **Graphe** | `backend/app/services/graph/engine.py` | Notions + prérequis en DAG. Propage la maîtrise, verrouille ce qui n'est pas prêt, et diagnostique : *« tu bloques sur Doctrine parce que les jointures SQL sont à 34 % »*. |
| **RAG** | `backend/app/services/rag/` | PDF/DOCX/MD → extraction → chunks sémantiques → embeddings (fastembed, local et gratuit) → Qdrant. La recherche comprend le *sens*, pas les mots-clés. |

L'**AI Router** (`services/ai/router.py`) choisit le modèle par tâche : petit
modèle pour les flashcards (~90 % des appels), gros modèle uniquement pour ce
qui demande du raisonnement (audit CGE, roadmap). C'est lui qui protège ton
budget.

---

## 📂 Structure

```
REVISIO-3.0/
├── docker-compose.yml            # Postgres + Qdrant + backend (+ frontend en profil "full")
├── docker-compose.override.yml   # Confort dev : hot-reload du backend
├── .env.example                  # Toutes les variables, documentées
│
├── backend/
│   ├── app/
│   │   ├── api/v1/               # Endpoints (auth, cards, documents, chat, …)
│   │   ├── core/                 # Config, DB, sécurité JWT, logging
│   │   ├── models/               # Tables SQLAlchemy
│   │   ├── schemas/              # Contrats Pydantic de l'API
│   │   └── services/             # ai/ · rag/ · srs/ · graph/ · seed.py
│   ├── alembic/                  # Migrations de schéma
│   └── tests/                    # Logique pure : SM-2, splitter, référentiel
│
└── frontend/
    └── src/
        ├── app/                  # Pages (dashboard, review, brain, chat, roadmap, stats)
        ├── components/           # UI soft-design + navigation + heatmap
        ├── lib/                  # Client API typé, auth, utils
        └── types/                # Miroirs TS des schémas backend
```

---

## 🛠 Commandes utiles

```bash
# Logs du backend en direct
docker compose logs -f backend

# Lancer les tests backend
docker compose exec backend sh -c "pip install -r requirements-dev.txt -q && pytest"

# Nouvelle migration après modification d'un modèle
docker compose exec backend alembic revision --autogenerate -m "description"
docker compose exec backend alembic upgrade head

# Tout arrêter / tout remettre à zéro (⚠️ supprime les données)
docker compose down
docker compose down -v

# Stack complète dans Docker (frontend inclus)
docker compose --profile full up -d --build
```

---

## 🗺 Roadmap (état actuel : fin de phase 2)

- [x] **Phase 1 — Fondations** : Docker Compose, auth JWT, modèles, migrations, UI de base
- [x] **Phase 2 — RAG** : import PDF/DOCX/MD, chunks, embeddings, Qdrant, AI Router + mode simulé
- [x] **Phase 3 (partiel) — Graphe & SRS** : SM-2 complet, graphe + diagnostic, heatmap, skill tree en liste
- [ ] Phase 3 (suite) : visualisation interactive du graphe (React Flow), FSRS
- [ ] Phase 4 : sandbox SQL, générateur de TP, roadmap IA persistée, mode Focus chronométré
- [ ] Phase 5 : PWA offline, CI GitHub Actions, déploiement VPS (Nginx + HTTPS + backups)

---

## 🧯 Dépannage

| Symptôme | Cause probable | Remède |
| --- | --- | --- |
| `backend` redémarre en boucle | PostgreSQL pas encore prêt | Il attend le healthcheck ; regarde `docker compose logs backend` |
| Premier import de document très lent | fastembed télécharge son modèle (~130 Mo), une seule fois | Attendre ; le cache est dans un volume Docker |
| « Backend injoignable » dans l'app | Stack arrêtée | `docker compose up -d` |
| Port 5433/6333/8000 occupé | Autre service local | Change le port dans `.env` |
| Réponses IA « simulées » | `AI_MOCK=true` ou clé absente | Voir l'encart plus haut ; état visible sur `/api/v1/ai/status` |
