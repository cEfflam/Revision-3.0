# 📊 Avancement de REVISIO

> Mis à jour à chaque session de travail. Dernière mise à jour : **2026-08-07**.

**Les quatre méthodes d'apprentissage sont livrées.** L'application est
utilisable de bout en bout et prête à être testée pour de vrai.

| | |
| --- | --- |
| Fonctionnalités d'apprentissage | **~97 %** |
| Mise en production (phase 5) | **5 %** |

> **Ce n'est pas 100 %, et voici exactement ce qui manque** — aucun de ces
> points n'empêche de travailler avec l'application aujourd'hui :
> graphe visuel React Flow · FSRS · OCR · injection automatique au graphe à
> l'import · assistant de premier lancement · écran de réglages ·
> CI/CD, déploiement VPS et sauvegardes · les trois points de cohérence
> ⚠️ listés en bas de page.

> ⚙️ **Application mono-utilisateur.** Conçue pour un seul apprenant. La mise
> en ligne servira à y accéder depuis plusieurs appareils, pas à ouvrir des
> comptes. Ça simplifie beaucoup : pas de quotas, pas de partage, et le
> « profil apprenant » injecté dans les prompts est toujours le même.

| Phase | État | Détail |
| --- | --- | --- |
| 1 · Fondations | ✅ **100 %** | Docker, auth, modèles, migrations, UI |
| 2 · RAG & import | ✅ **100 %** | PDF/DOCX/MD, Qdrant, embeddings locaux, AI Router |
| 3 · Graphe & SRS | 🟡 **75 %** | SM-2 ✅, graphe + diagnostic ✅ · manque React Flow, FSRS |
| 4 · Moteurs & Roadmap IA | ✅ **100 %** | + entraînement BTS, Feynman, sandboxes SQL et pseudo-code |
| 5 · Polish & déploiement | ❌ **5 %** | Manifest PWA seul · manque CI/CD, VPS, backups |

## 🧠 Les méthodes d'apprentissage, et où elles vivent

| Méthode | Implémentée | Où exactement |
| --- | :---: | --- |
| **Active Recall** (effet de test) | ✅ | `/review` : la question s'affiche seule, la réponse n'apparaît qu'après l'effort. Quiz et entraînement BTS reposent sur le même principe. |
| **Répétition espacée** | ✅ | `services/srs/sm2.py` — SM-2 complet, 4 états, intervalles calculés sur la courbe d'Ebbinghaus. 7 tests. |
| **Interleaving** | ✅ | `srs/service.py::_interleave_by_subject` — round-robin sur les matières dans la file. Désactivé sur une session ciblée (une seule matière). |
| **Feynman / auto-explication** | ✅ | Panneau dédié sous chaque notion du référentiel. Tu expliques avec tes mots ; l'IA classe chaque point (acquis / flou / manquant / erroné), cite le passage exact de ton cours et pose une question — jamais la réponse. Indice de fluidité sur 100. |
| **Retrieval practice** | ✅ | Toute la file SRS + le quiz + les sujets d'examen. |
| **Difficulté adaptative** | ✅ | `ease_factor` par carte, `mastery` par nœud, verrouillage des prérequis. |
| **Analyse des erreurs** | 🟡 | Diagnostic des prérequis ✅, prompt `error_analysis` ✅ · pas d'écran dédié. |

---

## ✅ Fait et vérifié

| Fonctionnalité | Vérifié comment |
| --- | --- |
| Authentification JWT + compte de démo | Parcours navigateur complet |
| Onboarding (objectif, niveaux, temps) | Formulaire → 51 nœuds créés |
| Dashboard « Aujourd'hui » | Actions priorisées côté serveur |
| Révision SRS (Active Recall) | Question → réponse → 4 notes → replanification |
| Import de documents (RAG) | Markdown ingéré, 2 fragments, 2 vecteurs |
| Recherche sémantique | Score 0.54 sur requête sans mot commun |
| Génération de flashcards par IA | 4 cartes créées depuis un document |
| Graphe + diagnostic des prérequis | 51 nœuds, 47 arêtes, 41 verrouillés |
| Heatmap, streak, statistiques | Carte des compétences par matière |
| **Audit d'écrit CGE** | Surlignage warning/info/global validé au navigateur |
| Contrôle du coût IA | Raisonnement ciblé, plafonds, chiffrage par appel |
| Routage par matière | Qwen (français/CEJM/JSON) · DeepSeek (maths/algo/code) |
| **Sélection par matière** | `/subjects` + détail, barres de stats cliquables |
| **Mode Focus chronométré** | Chrono décompté, file ciblée par matière ou notion |
| **Quiz dynamique** | Généré depuis un cours, score et explications |
| **Roadmap IA** | Parcours ordonné persisté, étapes cochables |
| **Gestion des cartes** | Correction, suspension (sort de la file), suppression |
| **Entraînement type BTS** | Sujet CEJM généré dans le style d'une vraie annale, corrigé 0/20 puis 2/20 avec justification par question |
| **IA réelle** | Qwen 0,000036 $/appel · DeepSeek 0,000127 $ (332 jetons de réflexion) |
| **Structure des PDF** | 0/211 fragments titrés → **182/182** sur une fiche de 1,3 Mo |
| **Anti-doublon au graphe** | 2ᵉ import du même document : 0 notion inconnue |
| **Référentiel hiérarchique** | Matière > Thème > Notion, cycles refusés |
| **Boucle examen → maîtrise** | 84,4 % → 21,1 % après un 0/20, 2 cartes ramenées en file |
| **Profil dans le prompt** | L'IA reçoit les notions fragiles et acquises à chaque échange |
| **Synthèse par notion** | Note consolidée citant ses sources, récupération à deux étages |
| **Relecture IA de la synthèse** | 3 erreurs plantées sur 3 détectées, 0 faux positif |
| **Décroissance de maîtrise** | Une notion à 85 % il y a 6 mois passe derrière une à 70 % d'hier |
| **Arbre du référentiel éditable** | Thème créé, notion déplacée, « À classer » vidé — au navigateur |
| **Synthèse + relecture dans l'UI** | Génération, affichage, relecture « fiable / 0 remarque » |
| **Technique Feynman** | Explication volontairement vague → fluidité 35/100, 5 lacunes localisées, verdict « il récite des mots sans les expliquer » |
| **Sandbox SQL** | Exercice clients/projets généré en 63 s, piège NULL inclus ; INNER JOIN → 7 lignes au lieu de 8, LEFT JOIN correct, `DROP TABLE` refusé pédagogiquement |
| **Sandbox pseudo-code** | Bug `max <- 0` trouvé sur tableau de négatifs **et** cas limite `n = 0`, trace en 4 étapes |
| **RAG restreint à la notion** | Filtre par documents rattachés (± 2 niveaux d'enfants), le filtre matière est levé dès qu'une notion est ciblée |
| Tests backend | **51/51** (SM-2, découpage, référentiel, JSON, appariement, décroissance, boucle examen) |

---

## 🔜 Prochaines étapes, par priorité

### 1. ✅ Sélection ciblée d'une matière ou d'un thème
*Demandé le 2026-08-05, livré le 2026-08-06.*

- [x] Barres de `/stats` cliquables → écran de la matière
- [x] `/subjects` : toutes les matières, la plus fragile en tête
- [x] `/subjects/[matière]` : notions, points faibles, cours, conseil d'attaque
- [x] Session ciblée `?subject=` ou `?node=` avec chronomètre `?focus=`
- [x] Quiz généré sur la matière ou le cours sélectionné

### 1bis. ✅ Écran d'édition du référentiel — **livré le 2026-08-06**

- [x] Hiérarchie `Matière > Thème > Notion` en base (`parent_id`, migration 0004)
- [x] `GET /subjects/{matière}/curriculum` — l'arbre, avec les notions « à classer »
- [x] `PATCH /nodes/{id}` avec `parent_id` — ranger, sortir, refuser les cycles
- [x] Rattachement d'un document à des notions existantes (anti-doublon)
- [x] **Arbre éditable** dans `/subjects/[matière]`, onglet « Mon référentiel » :
      créer un thème, ajouter une notion, renommer, déplacer, supprimer
- [x] Panneau de synthèse + relecture IA au clic sur une notion
- [x] Panneau de rattachement branché dans le Brain *(il était écrit, jamais utilisé)*
- [x] Restreindre la recherche RAG au thème en cours de travail

> **Déplacement par sélection, pas par glisser-déposer** : sur un arbre à
> plusieurs niveaux, le glisser-déposer est pénible au doigt et ambigu
> (dépose-t-on *dans* le thème ou *à côté* ?). Deux clics explicites valent
> mieux qu'un geste approximatif.

> **Décision structurante :** le référentiel est **écrit à la main**, pas généré.
> Le programme du BTS est fixe et connu ; le deviner à chaque import produit
> des doublons et une granularité incohérente. L'IA aide à *ranger* dans ce
> squelette, elle ne le fabrique pas.

### 1ter. ✅ Synthèse consolidée par notion — **livrée le 2026-08-06**

- [x] Champs `synthesis`, `synthesis_updated_at`, `synthesis_source_count` (migration 0005)
- [x] `POST /nodes/{id}/synthesis` — fusionne tous les documents rattachés
- [x] Récupération à **deux étages** : synthèse pour le sens, 3 fragments bruts pour le détail exact
- [x] Détection de péremption : si des documents ont été rattachés depuis
- [ ] Régénération automatique quand un document change *(manuelle pour l'instant)*
- [ ] Bouton dans l'interface *(API seule pour l'instant)*

**Mesuré** sur « Les opérateurs logiques fondamentaux » :

| | Fragments seuls | Synthèse + 3 fragments |
| --- | ---: | ---: |
| Jetons | 2 056 | **1 986** |
| Sources | 6 (qui se recoupent) | 3 (précises) |

> **Honnêteté sur le gain** : l'économie de jetons est marginale (3 %). Le vrai
> bénéfice est ailleurs — l'IA reçoit un modèle mental *ordonné* de la notion
> plutôt que six extraits qui se chevauchent, et les fragments restants
> servent au détail exact. Le gain devient net quand la recherche vectorielle
> échoue : la synthèse répond alors seule, là où le RAG seul rendait 0 source.
>
> **Le piège évité** : une synthèse est *lossy*. Les fragments bruts sont
> conservés pour l'article de loi exact et la syntaxe précise.

### 2. ✅ Technique Feynman — **livrée le 2026-08-07**

Les quatre temps de la méthode, dans l'ordre :
1. **Choisir une notion** — l'arbre du référentiel.
2. **Expliquer avec ses mots**, comme à un enfant de 10 ans, sans jargon.
3. **Repérer les blocages** — l'IA compare au cours et classe chaque point :
   acquis, flou, manquant, erroné, avec le passage exact du cours.
4. **Recommencer** — bouton « Réexpliquer après avoir relu ».

> **Pas de bouton « voir la réponse », volontairement.** Chaque lacune
> s'accompagne d'une *question* qui pousse à la combler soi-même. La méthode
> ne vaut que si l'effort est fourni — un corrigé la vide de son sens.

- [ ] Historique des tentatives et courbe de fluidité dans le temps
      *(l'intérêt propre de la méthode ; aujourd'hui chaque tentative est
      isolée et seule la maîtrise du nœud garde une trace)*

### 2bis. ✅ Bacs à sable SQL et pseudo-code — **livrés le 2026-08-07**

- [x] `POST /sandbox/sql/exercise` — schéma, jeu de données et solution, avec
      un piège délibéré ; l'exercice est rejeté si sa propre solution échoue
- [x] `POST /sandbox/sql/run` — **exécution réelle** en SQLite mémoire,
      comparaison des ensembles de lignes sans tenir compte de l'ordre
- [x] `POST /sandbox/pseudocode` — trace pas à pas, erreurs, complexité
- [x] Écran `/sandbox` à deux onglets

> **Pourquoi SQLite et non PostgreSQL** : la base de l'exercice est montée en
> mémoire et détruite aussitôt. Aucune requête d'étudiant n'approche des
> données de l'application. Les mots-clés d'écriture sont refusés avec un
> message pédagogique, avec 3 s et 2 M d'instructions comme plafonds.

> **C'est le résultat qui juge, pas la requête.** Deux formulations
> différentes qui renvoient le même ensemble de lignes sont toutes deux
> justes — c'est exactement la réalité de SQL.

### 3. Référentiel détaillé par thème
*Demandé le 2026-08-05.* Le graphe actuel a 51 nœuds génériques. Objectif :
les **thèmes exacts du programme**, chacun avec sa méthode de révision propre
(un cas pratique CEJM ne se révise pas comme une jointure SQL).

- [ ] Détailler le référentiel matière par matière
- [ ] Associer à chaque type de nœud sa méthode d'entraînement

### 3bis. Assistant de premier lancement — *après les 100 %*
*Demandé le 2026-08-06.* Aujourd'hui, démarrer suppose d'éditer un `.env` à la
main. Pour une application qu'on télécharge et qu'on lance, c'est une barrière.

- [ ] Détection du premier démarrage (aucun utilisateur en base)
- [ ] Écran web : saisie de la clé OpenRouter, choix des deux modèles, test
      de connexion immédiat
- [ ] Écriture des réglages en base plutôt que dans le `.env`
- [ ] Variante ligne de commande pour le même parcours

### 4. Écran de réglages dans l'application
*Demandé le 2026-08-05.* Aujourd'hui, ajuster un plafond de jetons ou basculer
une matière d'un modèle à l'autre demande d'éditer le code et de redémarrer.

- [ ] Régler `MAX_TOKENS` par tâche depuis l'interface
- [ ] Basculer `AI_REASONING` sans redémarrer
- [ ] Choisir le modèle par rôle
- [ ] Voir la consommation réelle du mois (jetons + coût), pas seulement dans les logs

> Suppose de persister ces réglages en base plutôt que dans le `.env`, et
> d'ajouter une table de suivi de consommation.

### 4. Le reste
- [x] ~~Édition / suppression / suspension de cartes~~
- [x] ~~Générateur de roadmap IA~~
- [x] ~~Mode Focus chronométré~~
- [x] ~~Quiz dynamique~~
- [x] ~~Sandbox SQL *(exécution réelle des requêtes)*~~
- [ ] Graphe visuel React Flow *(termine la phase 3)*
- [ ] Injection auto dans le graphe à l'import *(`suggest_nodes()` jamais appelée)*
- [ ] FSRS, OCR
- [ ] CI GitHub Actions, déploiement VPS, sauvegardes

---

## 🚀 Comment tester

```bash
docker compose up -d              # backend + PostgreSQL + Qdrant
npm run dev --prefix frontend -- -p 3010
```

Puis `http://localhost:3010`, compte de démo `demo@revisio.app`.

> **Port 3010 et non 3000** : les serveurs de développement LaMeDuSe occupent
> déjà 3000, 3002 et 3003 sur cette machine.

**Ce à quoi s'attendre.** Les tâches de raisonnement (exercice SQL, relecture
d'algorithme, correction de copie, Feynman) prennent **30 à 90 secondes** :
le modèle déroule sa réflexion avant d'écrire. Mesuré : 63 s pour un exercice
SQL complet. Un compteur d'attente l'affiche désormais à l'écran — sans lui,
on croit que c'est planté et on recharge.

**Fournisseur d'IA.** OpenRouter, avec Qwen 3.7 Flash sur le français et le
JSON, DeepSeek V4 Flash avec raisonnement sur les maths, l'algorithmique et
le code. Gemini via Google AI Studio a été étudié le 2026-08-07 et **écarté** :
le palier sans frais plafonne à 20 requêtes par jour, ce qu'un seul import de
cours consomme.

---

## 🔍 Problèmes de cohérence identifiés

Revue menée le 2026-08-06, à la demande d'Efflam.

| # | Problème | État |
| --- | --- | --- |
| 1 | **La maîtrise ne décroissait jamais.** Une notion validée il y a six mois restait affichée à 90 % et n'était jamais reproposée — alors que c'est celle qu'on a oubliée. Le SRS gérait l'oubli des *cartes*, rien ne gérait celui des *notions*. | ✅ corrigé (demi-vie 90 j) |
| 2 | **Cartes orphelines.** Les cartes générées depuis un cours n'étaient rattachées à aucune notion : les réviser ne faisait progresser aucune maîtrise. Trou silencieux. | ✅ corrigé |
| 3 | **Matière incohérente.** Une notion rangée sous un thème gardait sa matière d'origine — « Algèbre de Boole » pouvait se retrouver en CEJM. | ✅ corrigé (héritage du parent) |
| 4 | **CORS à liste figée.** Next bascule de port quand 3000 est pris ; le navigateur recevait un « Failed to fetch » indistinguable d'un backend éteint. | ✅ corrigé (tout localhost en dev) |
| 5 | **`readiness` du dashboard = moyenne plate** sur les 55 notions, dont la plupart jamais touchées. Le chiffre bouge à peine et ignore les coefficients d'épreuve. | ⚠️ à revoir |
| 6 | **Le verrouillage est à sens unique.** `recompute_locks` ne verrouille que les nœuds jamais travaillés : une notion entamée ne se re-verrouille plus si ses prérequis s'effondrent. Défendable, mais à assumer explicitement. | ⚠️ à trancher |
| 7 | **La boucle examen dépend du client.** `target_node_ids` transite par le navigateur : un client qui ne renvoie pas l'objet intact casse silencieusement la rétroaction. Acceptable en mono-utilisateur, fragile sinon. | ⚠️ noté |

## 🧾 Dette technique

| Point | Gravité |
| --- | --- |
| Aucun test d'API (seulement la logique pure) | 🟠 |
| JWT en `localStorage` (vulnérable au XSS) | 🟡 acceptable en solo |
| Types TS recopiés à la main | 🟡 |
| Migration auto au démarrage | 🟡 pratique en dev, à revoir en prod |
| Chaîne de repli IA à un seul maillon | 🟡 depuis l'unification sur DeepSeek |
