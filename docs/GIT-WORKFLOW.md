# 🔀 Workflow Git & conventions

> Mémo DevOps du projet. À suivre pour que l'historique reste lisible dans
> six mois — c'est-à-dire quand tu en auras vraiment besoin.

---

## 1. Conventional Commits

Chaque message suit le format :

```
<type>(<portée>): <résumé à l'impératif, minuscule, sans point final>

<corps facultatif : le POURQUOI, pas le comment>
```

### Les types

| Type | Quand l'utiliser | Exemple |
| --- | --- | --- |
| `feat` | Nouvelle fonctionnalité visible | `feat(srs): ajouter l'algorithme FSRS` |
| `fix` | Correction de bug | `fix(rag): éviter le débordement des fragments` |
| `refactor` | Réécriture sans changement de comportement | `refactor(api): extraire la validation` |
| `perf` | Amélioration de performance | `perf(srs): indexer la file de révision` |
| `test` | Ajout ou correction de tests | `test(graph): couvrir la détection de cycles` |
| `docs` | Documentation seule | `docs: documenter le déploiement VPS` |
| `style` | Formatage, sans impact logique | `style: appliquer ruff format` |
| `chore` | Outillage, dépendances, config | `chore: monter Next.js en 15.2` |
| `ci` | Pipeline d'intégration continue | `ci: lancer pytest sur chaque PR` |
| `build` | Système de build, Docker | `build: réduire l'image backend` |

### Les portées du projet

`infra` · `backend` · `frontend` · `api` · `srs` · `graph` · `rag` · `ai` · `db`

### La règle qui compte

Le **titre** dit *quoi*. Le **corps** dit *pourquoi*.

Le « comment » est déjà dans le diff — le répéter en prose ne sert à rien.
Ce que le diff ne dira jamais, c'est la raison d'un choix :

```
fix(rag): ne pas laisser le chevauchement déborder de max_chars

Le fragment précédent + le chevauchement pouvait dépasser la limite alors
que le fragment seul la respectait. Le modèle d'embeddings tronquait alors
la fin en silence, et l'information perdue devenait introuvable.
Quand ça déborde, on sacrifie le chevauchement : une frontière sans
recouvrement coûte moins cher qu'un fragment amputé.
```

---

## 2. Branches

| Branche | Rôle |
| --- | --- |
| `main` | Toujours fonctionnelle. C'est elle qui part en production. |
| `feat/<nom>` | Une fonctionnalité en cours |
| `fix/<nom>` | Une correction |

```bash
# Démarrer une fonctionnalité
git switch -c feat/graphe-react-flow

# Travailler, committer par étapes logiques…
git add frontend/src/app/\(app\)/roadmap/
git commit -m "feat(graph): afficher le graphe avec React Flow"

# Publier la branche
git push -u origin feat/graphe-react-flow
```

Puis ouvrir une Pull Request sur GitHub, même en solo : ça force à relire son
propre diff avant de fusionner, et c'est là qu'on repère la moitié de ses
erreurs.

```bash
gh pr create --fill
gh pr merge --squash --delete-branch
```

**`--squash`** écrase les commits de la branche en un seul sur `main`.
Résultat : `main` raconte l'histoire des fonctionnalités, pas celle de tes
tâtonnements.

---

## 3. Avant chaque commit

```bash
# Backend : lint + tests
docker compose exec backend sh -c "ruff check app && python -m pytest -q"

# Frontend : le build vérifie tout le TypeScript
cd frontend && npm run build
```

---

## 4. Règles de sécurité

| Règle | Pourquoi |
| --- | --- |
| **Jamais de `.env` commité** | Il contient `SECRET_KEY` et tes clés d'API |
| **Jamais de token dans une commande** | Il resterait dans l'historique du shell |
| **`gh auth login` plutôt qu'un token dans l'URL du remote** | Le token serait écrit en clair dans `.git/config` |
| **Un secret exposé est un secret mort** | Le révoquer, ne jamais « juste le retirer » : il reste dans l'historique Git et dans les logs |

Vérifier avant de pousser :

```bash
git ls-files | grep -E "^\.env$"          # doit ne rien renvoyer
git log -p --all | grep -E "ghp_[A-Za-z0-9]{30,}"   # doit ne rien renvoyer
```

---

## 5. Les commandes du quotidien

```bash
git status                      # où j'en suis
git diff                        # ce que j'ai modifié, pas encore indexé
git diff --staged               # ce qui partira au prochain commit
git add -p                      # indexer morceau par morceau (excellent réflexe)
git log --oneline --graph       # l'historique en un coup d'œil
git commit --amend              # corriger le DERNIER commit, s'il n'est pas poussé
git restore <fichier>           # annuler mes modifications sur un fichier
git restore --staged <fichier>  # désindexer sans perdre les modifications
```

> ⚠️ `--amend` et `reset` réécrivent l'historique. Sans danger tant que le
> commit n'est pas poussé. Après un push, ils obligent à un `push --force`,
> qui écrase le travail des autres — ici tu es seul, mais autant prendre
> l'habitude tout de suite.
