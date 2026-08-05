# 💸 Ce que coûte REVISIO en usage réel

> Chiffrage pour une utilisation **quotidienne, 30 jours sur 30**.
> Tarifs OpenRouter au 2026-08-05, en dollars par million de jetons.

---

## 1. Les tarifs

| Rôle | Modèle | Entrée | Sortie |
| --- | --- | --- | --- |
| `language` | `qwen/qwen3.7-flash` | $0,03 / 1M | $0,13 / 1M |
| `reasoning` | `deepseek/deepseek-v4-flash-0731` | $0,09 / 1M | $0,18 / 1M |

**Les jetons de réflexion sont facturés au tarif de sortie.** C'est le point
qui décide de tout : sur DeepSeek, réfléchir coûte $0,18 le million, soit six
fois le prix d'un jeton d'entrée chez Qwen.

> 🎁 **Les embeddings sont gratuits.** fastembed tourne en local dans le
> conteneur : indexer 500 pages de cours ne coûte rien. C'est le poste qui
> ruine la plupart des projets RAG, et il est à zéro ici.

---

## 2. Hypothèses d'usage

Un étudiant de BTS SIO qui travaille ~45 min par jour :

| Action | Fréquence | Rôle |
| --- | --- | --- |
| Questions au coach sur les cours | 5 / jour | language |
| Guidage en maths | 3 / jour | reasoning |
| Journal du soir | 1 / jour | language |
| Génération de flashcards | 3 / semaine | language |
| Analyse de code | 1 / jour | reasoning |
| Correction SQL | 5 / semaine | reasoning |
| Audit d'écrit CGE | 2 / semaine | language |
| Import + résumé de document | 2 / semaine | language |

---

## 3. Le résultat

### Rôle `language` — Qwen

| Tâche | Appels / mois | Entrée | Sortie |
| --- | ---: | ---: | ---: |
| Chat sur les cours | 150 | 300 000 | 75 000 |
| Flashcards | 13 | 32 500 | 15 600 |
| Audit CGE | 8 | 32 000 | 12 000 |
| Résumés d'import | 8 | 24 000 | 3 200 |
| Journal du soir | 30 | 9 000 | 6 000 |
| **Total** | **209** | **397 500** | **111 800** |

Coût : (0,398 × $0,03) + (0,112 × $0,13) = **$0,027**

### Rôle `reasoning` — DeepSeek

La réflexion est incluse dans la sortie (~1 500 jetons par appel).

| Tâche | Appels / mois | Entrée | Sortie *(réflexion incl.)* |
| --- | ---: | ---: | ---: |
| Guidage maths | 90 | 72 000 | 189 000 |
| Analyse de code | 30 | 45 000 | 81 000 |
| Correction SQL | 20 | 24 000 | 40 000 |
| **Total** | **140** | **141 000** | **310 000** |

Coût : (0,141 × $0,09) + (0,310 × $0,18) = **$0,069**

### 🧾 Total mensuel

| | Coût |
| --- | ---: |
| Qwen (rédaction, français, JSON) | $0,027 |
| DeepSeek (maths, code, logique) | $0,069 |
| Embeddings (local) | $0,00 |
| **TOTAL** | **≈ $0,10 / mois** |

**Dix centimes par mois.** Même en multipliant l'usage par cinq — révisions
intensives avant l'examen — on reste sous **$0,50**.

---

## 4. Pourquoi c'est si bas

| Décision | Économie |
| --- | ---: |
| Raisonnement coupé sur les tâches de langue | **~70 %** |
| Embeddings en local plutôt qu'en API | ~$2 / mois évités |
| Le RAG envoie 4 extraits, pas le document entier | ~85 % sur l'entrée |
| Plafonds `max_tokens` par tâche | ~20 % sur la sortie |
| Historique de conversation limité à 5 échanges | croissance linéaire évitée |

### Le contre-exemple qui fait mal

Si le raisonnement était activé **partout** (le réglage par défaut de beaucoup
de projets) :

- les 209 appels `language` produiraient ~1 500 jetons de réflexion chacun,
- soit **+313 500 jetons de sortie** facturés,
- pour un gain de qualité **nul** : reformater un texte fourni ne demande
  aucune réflexion.

Coût dans ce cas : **~$0,15 / mois** au lieu de $0,10, soit **+50 %** pour rien.
L'écart paraît dérisoire à cette échelle — il ne l'est plus du tout sur une
application à mille utilisateurs, et c'est le même réflexe qui protège.

---

## 5. Vérifier la réalité

Chaque appel est chiffré dans les logs :

```bash
docker compose logs backend | grep "coût"
```

Format de la ligne :

```
coût | math_hint | deepseek/deepseek-v4-flash-0731 | entrée 812 (0 en cache) | sortie 2104 (1487 de réflexion) | 0.000452 $ | 3120 ms
```

Le total réel se lit sur ton tableau de bord OpenRouter. Si l'écart avec cette
estimation est important, c'est que les hypothèses d'usage ci-dessus ne
correspondent pas à ta pratique — pas que le calcul est faux.

---

## 6. Les leviers si ça dérape

Dans l'ordre du plus efficace au moins efficace :

1. **`AI_REASONING=false`** dans le `.env` → coupe toute la réflexion, divise
   la facture par ~3. La qualité baisse en maths, le reste ne bouge pas.
2. **Réduire `MAX_TOKENS`** dans `router.py` pour la tâche coûteuse identifiée
   dans les logs.
3. **Basculer une tâche de `reasoning` vers `language`** dans `TASK_ROLE`.
4. **Réduire `RAG_TOP_K`** (6 → 4) : moins d'extraits, moins d'entrée.

---

## 7. Sur les plafonds actuels

Question légitime : 400 jetons pour un journal du soir, est-ce trop peu ?

**Repère : 1 jeton ≈ 0,75 mot en français.**

| Tâche | Plafond | Équivalent | Verdict |
| --- | ---: | --- | --- |
| Journal du soir | 500 | ~375 mots | Large — le prompt en demande 5 lignes |
| Résumé de document | 800 | ~600 mots | Suffisant pour 3 points clés |
| Flashcards | 2 000 | ~1 500 mots | ~10 cartes complètes |
| Audit CGE | 3 000 | ~2 250 mots | JSON de 6-8 problèmes détaillés |
| Guidage maths | 2 500 | réflexion incl. | ~1 500 de réflexion + réponse |
| Analyse de code | 3 500 | réflexion incl. | Le plus large, à raison |

Les plafonds des tâches de raisonnement ont été relevés : la réflexion
s'impute sur le même budget, et une borne trop basse tronquerait la réponse
**après** que le modèle a déjà payé sa réflexion — le pire des deux mondes.

> 🔜 **Prévu** : un écran de réglages dans l'application pour ajuster ces
> valeurs sans toucher au code. Noté dans [AVANCEMENT.md](AVANCEMENT.md).
