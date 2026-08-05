# 🧠 REVISIO (AI Learning OS)
> **Cahier des Charges Technique & Fonctionnel (V1.0)**
> *Un Operating System d'apprentissage personnel piloté par IA, graphe de connaissances et RAG vectoriel.*

---

## 🎯 1. Vision & Philosophie du Projet

- **Objectif Principal** : Ne pas créer une simple application de révision temporaire, mais un **OS d'apprentissage à vie**.
- **Logique Métier** : Travailler par **compétences et dépendances** (Knowledge Graph) plutôt que par de simples notes ou fiches isolées.
- **Approche Pédagogique** : Intégration native des meilleures sciences de l'apprentissage (*Spaced Repetition, Active Recall, Interleaving, Feynman Technique, Retrieval Practice*).
- **Évolution** : D'un cursus BTS SIO immédiat vers des objectifs futurs (DevOps, Cloud, Certifications AWS, Python, Anglais/TOEIC, etc.).

---

## 🏗️ 2. Architecture Technique & Stack

```
                 +-----------------------------------+
                 |         Frontend (PWA)            |
                 |  Next.js 15 (App Router) / TS     |
                 |  Tailwind CSS + design soft UI    |
                 +-----------------+-----------------+
                                   |
                                   v REST
                 +-----------------+-----------------+
                 |         Backend FastAPI           |
                 |      Python 3.12 / Pydantic v2    |
                 +--------+----------------+---------+
                          |                |
         +----------------+                +----------------+
         v                                                  v
+-------------------------+                 +---------------------------+
|   Base Relationnelle    |                 |   Base Vectorielle (RAG)  |
| PostgreSQL (SQLAlchemy) |                 |          Qdrant           |
| Users, Graphe, SRS,     |                 | Chunks, Embeddings,       |
| Sessions, Stats         |                 | Collections par domaine   |
+-------------------------+                 +------------+--------------+
                                                         |
                                                         v
                                            +------------+------------+
                                            |      AI Orchestrator    |
                                            |     (OpenRouter API)    |
                                            |  DeepSeek / Qwen / etc. |
                                            +-------------------------+
```

### Stack retenue
- **Frontend** : Next.js 15 (App Router), TypeScript, Tailwind CSS, Framer Motion, Lucide, PWA.
- **Backend** : FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic v2.
- **Bases** : PostgreSQL (structuré) + Qdrant (vectoriel).
- **IA** : OpenRouter avec routage par coût (cheap / standard / reasoning) et mode simulé (`AI_MOCK`).
- **Embeddings** : fastembed en local (multilingual-e5-small), OpenAI en option.
- **DevOps** : Docker Compose, GitHub Actions (à venir), VPS Nginx/HTTPS (à venir).

---

## 🧱 3. Core Modules

### A. Knowledge Graph
- DAG de notions : chaque concept est un nœud relié à ses prérequis.
- Verrouillage dynamique (une notion s'ouvre quand ses prérequis dépassent 60 % de maîtrise).
- **Diagnostic** : en cas d'échec, remontée des prérequis faibles (« tu bloques sur Doctrine car les jointures SQL sont fragiles »).

### B. Moteurs par matière (prompts spécialisés)
1. **Dev** : analyse de code en 4 temps (intention, bug + cause, correctif, leçon).
2. **SQL** : correction pas-à-pas, pièges classiques, optimisation.
3. **Maths** : guidance socratique — ne JAMAIS donner la réponse.
4. **CEJM** : méthode juridique (faits, problème, règle, application, conclusion).
5. **CGE** : audit d'écrit avec problèmes localisés et citations exactes (surlignage).
6. **Anglais IT** : conversation B2 avec corrections inline annotées.

### C. Pipeline RAG
1. Extraction (PDF/DOCX/MD → Markdown structuré).
2. Découpage sémantique (titres → paragraphes → phrases, avec chevauchement).
3. Embeddings + insertion Qdrant (collections `course`, `exam`, `error`, `note`).
4. À l'import : résumé exécutif, flashcards, suggestions de nœuds.

---

## ⚡ 4. Killer Features
1. **SRS (SM-2 → FSRS)** : révision au moment exact où l'oubli menace.
2. **Diagnostic par le graphe** : la cause de l'échec, pas juste le constat.
3. **Journal & heatmap** : régularité visible, résumé du soir par l'IA.
4. **AI Router** : petit modèle pour 90 % des tâches, gros modèle pour le raisonnement.
5. **Dashboard « Aujourd'hui »** : actions priorisées côté serveur.

---

## 🗺️ 5. Roadmap
- **Phase 1 — Fondations** ✅ : Docker, auth, modèles, migrations, UI.
- **Phase 2 — RAG** ✅ : import, Qdrant, embeddings, AI Router.
- **Phase 3 — Graphe & SRS** 🟡 : SM-2 ✅, graphe + diagnostic ✅, React Flow et FSRS à venir.
- **Phase 4 — Moteurs & Roadmap IA** : sandbox SQL, générateur de TP, roadmap persistée, mode Focus.
- **Phase 5 — Polish & Déploiement** : PWA offline, CI/CD, VPS, backups.

---

## 🎨 6. Direction artistique (Soft UI)
- Fond `#F8F9FC`, cartes blanches `rounded-[28px]`, ombres diffuses.
- Accent unique : indigo `#6366F1`.
- Titres extra-bold `text-slate-800`, sous-titres `text-slate-400`.
- Listes d'actions style iOS : tuile d'icône lavande + chevron.
