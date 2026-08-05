# 📊 Avancement de REVISIO

> Mis à jour à chaque session de travail. Dernière mise à jour : **2026-08-05**.

**Global : ~65 %** du cahier des charges.

| Phase | État | Détail |
| --- | --- | --- |
| 1 · Fondations | ✅ **100 %** | Docker, auth, modèles, migrations, UI |
| 2 · RAG & import | ✅ **100 %** | PDF/DOCX/MD, Qdrant, embeddings locaux, AI Router |
| 3 · Graphe & SRS | 🟡 **70 %** | SM-2 ✅, graphe + diagnostic ✅ · manque React Flow, FSRS |
| 4 · Moteurs & Roadmap IA | 🟡 **45 %** | Audit CGE ✅ · manque sandbox SQL, roadmap IA, mode Focus |
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
| Tests backend | 17/17 (SM-2, découpage, référentiel) |

---

## 🔜 Prochaines étapes, par priorité

### 1. Sélection ciblée d'une matière ou d'un thème
*Demandé le 2026-08-05.* Aujourd'hui la révision est globale : on ne peut pas
choisir « je bosse les maths maintenant ».

- [ ] Cliquer une barre de la carte des compétences (`/stats`) → ouvrir la matière
- [ ] Écran par matière : cours synthétisés, notions, cartes, points faibles
- [ ] Lancer une session ciblée sur un thème précis
- [ ] Générer des exercices sur la notion sélectionnée

> L'API le permet déjà en partie : `/cards/queue?subject=`, `/nodes?subject=`,
> `/nodes/{id}/diagnosis`. Ce qui manque est surtout côté interface.

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
- [ ] Édition / suppression / suspension de cartes *(bloque l'usage quotidien)*
- [ ] Graphe visuel React Flow *(termine la phase 3)*
- [ ] Générateur de roadmap IA *(seule killer feature absente)*
- [ ] Mode Focus chronométré
- [ ] Quiz dynamique *(prompt écrit, aucun endpoint)*
- [ ] Injection auto dans le graphe à l'import *(`suggest_nodes()` jamais appelée)*
- [ ] FSRS, sandbox SQL, OCR
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
