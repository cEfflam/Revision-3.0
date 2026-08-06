# 📊 Avancement de REVISIO

> Mis à jour à chaque session de travail. Dernière mise à jour : **2026-08-06**.

**Global : ~92 %** du cahier des charges. **IA branchée en réel** (Qwen + DeepSeek).

> ⚙️ **Application mono-utilisateur.** Conçue pour un seul apprenant. La mise
> en ligne servira à y accéder depuis plusieurs appareils, pas à ouvrir des
> comptes. Ça simplifie beaucoup : pas de quotas, pas de partage, et le
> « profil apprenant » injecté dans les prompts est toujours le même.

| Phase | État | Détail |
| --- | --- | --- |
| 1 · Fondations | ✅ **100 %** | Docker, auth, modèles, migrations, UI |
| 2 · RAG & import | ✅ **100 %** | PDF/DOCX/MD, Qdrant, embeddings locaux, AI Router |
| 3 · Graphe & SRS | 🟡 **75 %** | SM-2 ✅, graphe + diagnostic ✅ · manque React Flow, FSRS |
| 4 · Moteurs & Roadmap IA | ✅ **95 %** | + entraînement type BTS · manque sandbox SQL |
| 5 · Polish & déploiement | ❌ **5 %** | Manifest PWA seul · manque CI/CD, VPS, backups |

## 🧠 Les méthodes d'apprentissage, et où elles vivent

| Méthode | Implémentée | Où exactement |
| --- | :---: | --- |
| **Active Recall** (effet de test) | ✅ | `/review` : la question s'affiche seule, la réponse n'apparaît qu'après l'effort. Quiz et entraînement BTS reposent sur le même principe. |
| **Répétition espacée** | ✅ | `services/srs/sm2.py` — SM-2 complet, 4 états, intervalles calculés sur la courbe d'Ebbinghaus. 7 tests. |
| **Interleaving** | ✅ | `srs/service.py::_interleave_by_subject` — round-robin sur les matières dans la file. Désactivé sur une session ciblée (une seule matière). |
| **Feynman / auto-explication** | 🟡 | Présent dans les prompts (reformuler avec ses mots, question de vérification finale) et via `hint` + `explanation` sur les cartes. **Pas encore d'écran dédié** où l'on explique à voix haute et se fait corriger. |
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
| Tests backend | 17/17 (SM-2, découpage, référentiel) |

---

## 🔜 Prochaines étapes, par priorité

### 1. ✅ Sélection ciblée d'une matière ou d'un thème
*Demandé le 2026-08-05, livré le 2026-08-06.*

- [x] Barres de `/stats` cliquables → écran de la matière
- [x] `/subjects` : toutes les matières, la plus fragile en tête
- [x] `/subjects/[matière]` : notions, points faibles, cours, conseil d'attaque
- [x] Session ciblée `?subject=` ou `?node=` avec chronomètre `?focus=`
- [x] Quiz généré sur la matière ou le cours sélectionné

### 1bis. Écran d'édition du référentiel — **la suite immédiate**
*Décidé le 2026-08-06.* L'API est complète, l'interface manque.

- [x] Hiérarchie `Matière > Thème > Notion` en base (`parent_id`, migration 0004)
- [x] `GET /subjects/{matière}/curriculum` — l'arbre, avec les notions « à classer »
- [x] `PATCH /nodes/{id}` avec `parent_id` — ranger, sortir, refuser les cycles
- [x] Rattachement d'un document à des notions existantes (anti-doublon)
- [ ] **Écran d'arbre éditable** : créer un thème, y glisser des notions, renommer
- [ ] Restreindre la recherche RAG au thème en cours de travail

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

### 2. Technique Feynman — écran dédié
*Idée notée le 2026-08-06.* Seule des quatre méthodes à n'être que partielle.

Le déroulé visé, fidèle à la méthode :
1. **Choisir une notion** dans le référentiel.
2. **Expliquer avec ses mots**, comme à un enfant de 10 ans, sans jargon.
3. **Repérer les blocages** : l'IA compare l'explication au cours et pointe ce
   qui est flou, absent ou faux — puis affiche le passage exact du cours.
4. **Recommencer** jusqu'à ce que ce soit limpide, avec un suivi des tentatives.

> À nuancer : une fois la notion réellement révisée, l'exercice se confond avec
> une carte SRS ouverte. L'intérêt propre est le *suivi de fluidité* dans le
> temps, pas l'explication isolée.

### 3. Référentiel détaillé par thème
*Demandé le 2026-08-05.* Le graphe actuel a 51 nœuds génériques. Objectif :
les **thèmes exacts du programme**, chacun avec sa méthode de révision propre
(un cas pratique CEJM ne se révise pas comme une jointure SQL).

- [ ] Détailler le référentiel matière par matière
- [ ] Associer à chaque type de nœud sa méthode d'entraînement

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
- [ ] Graphe visuel React Flow *(termine la phase 3)*
- [ ] Injection auto dans le graphe à l'import *(`suggest_nodes()` jamais appelée)*
- [ ] Sandbox SQL *(exécution réelle des requêtes)*
- [ ] FSRS, OCR
- [ ] CI GitHub Actions, déploiement VPS, sauvegardes

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
