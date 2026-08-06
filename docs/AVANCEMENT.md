# 📊 Avancement de REVISIO

> Mis à jour à chaque session de travail. Dernière mise à jour : **2026-08-06**.

**Global : ~82 %** du cahier des charges.

| Phase | État | Détail |
| --- | --- | --- |
| 1 · Fondations | ✅ **100 %** | Docker, auth, modèles, migrations, UI |
| 2 · RAG & import | ✅ **100 %** | PDF/DOCX/MD, Qdrant, embeddings locaux, AI Router |
| 3 · Graphe & SRS | 🟡 **75 %** | SM-2 ✅, graphe + diagnostic ✅ · manque React Flow, FSRS |
| 4 · Moteurs & Roadmap IA | ✅ **90 %** | Roadmap IA, Focus, quiz, CGE ✅ · manque sandbox SQL |
| 5 · Polish & déploiement | ❌ **5 %** | Manifest PWA seul · manque CI/CD, VPS, backups |

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

### 2. Référentiel détaillé par thème
*Demandé le 2026-08-05.* Le graphe actuel a 51 nœuds génériques. Objectif :
les **thèmes exacts du programme**, chacun avec sa méthode de révision propre
(un cas pratique CEJM ne se révise pas comme une jointure SQL).

- [ ] Détailler le référentiel matière par matière
- [ ] Associer à chaque type de nœud sa méthode d'entraînement

### 3. Écran de réglages dans l'application
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

## 🧾 Dette technique

| Point | Gravité |
| --- | --- |
| Aucun test d'API (seulement la logique pure) | 🟠 |
| JWT en `localStorage` (vulnérable au XSS) | 🟡 acceptable en solo |
| Types TS recopiés à la main | 🟡 |
| Migration auto au démarrage | 🟡 pratique en dev, à revoir en prod |
| Chaîne de repli IA à un seul maillon | 🟡 depuis l'unification sur DeepSeek |
