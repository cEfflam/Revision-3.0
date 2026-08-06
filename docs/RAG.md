# 🔍 Comment fonctionne le RAG de REVISIO

> RAG = *Retrieval-Augmented Generation*. En français : au lieu de laisser
> l'IA répondre de mémoire (et inventer), on va d'abord **chercher les
> passages pertinents dans TES cours**, puis on les lui donne à lire avant
> qu'elle réponde.

---

## 1. Le problème que ça résout

Sans RAG, si tu demandes « c'est quoi une clé étrangère ? », le modèle répond
avec ses connaissances générales. Trois défauts :

- il ne connaît pas **le cours de ton prof**, ses formulations, ses exemples ;
- il peut inventer avec aplomb (*hallucination*) ;
- il ne peut pas citer de source, donc tu ne peux pas le vérifier.

Avec le RAG, la question devient : *« Voici 4 extraits de SES documents.
Réponds en t'appuyant dessus, et cite tes sources. »*

---

## 2. La chaîne complète

```
   TON FICHIER (PDF, DOCX, MD, TXT)
            │
            ▼
   ①  EXTRACTION            extractors.py
      « des octets → du Markdown structuré »
            │
            ▼
   ②  DÉCOUPAGE             splitter.py
      « un gros texte → des fragments de ~1200 caractères »
            │
            ▼
   ③  VECTORISATION         embeddings.py
      « chaque fragment → 384 nombres qui encodent son SENS »
            │
            ├──────────────► ④a  QDRANT   (les 384 nombres)
            │                    qdrant.py
            │
            └──────────────► ④b  POSTGRESQL (le texte du fragment)
                                 models/content.py
```

Puis, à la recherche :

```
   TA QUESTION
        │
        ▼
   ③  VECTORISATION (la même fonction)
        │
        ▼
   ⑤  RECHERCHE PAR SIMILARITÉ     qdrant.py
      « quels vecteurs pointent dans la même direction ? »
        │
        ▼
   ⑥  ASSEMBLAGE DU CONTEXTE       pipeline.py → build_context()
      « [1] (Cours SQL — 3.2 Jointures) ... »
        │
        ▼
   ⑦  APPEL AU MODÈLE              ai/service.py → ask()
      système : « appuie-toi sur ces extraits, cite [1] [2] »
```

Le tout est orchestré par **`services/rag/pipeline.py`**.

---

## 3. Chaque étape en détail

### ① Extraction — `services/rag/extractors.py`

> **Point important : les modèles ne lisent jamais ton PDF.** Ni Qwen ni
> DeepSeek ne reçoivent le fichier. Tout se passe **en local, gratuitement**,
> avant le moindre appel réseau : le PDF est converti en texte par `pypdf`
> dans le conteneur, découpé, puis vectorisé par fastembed — lui aussi local.
> Seuls partent à l'IA les 4 à 6 fragments retenus par la recherche, soit
> quelques milliers de caractères sur un document qui peut en faire 150 000.
>
> **Convertir toi-même en .txt ne ferait donc économiser aucun jeton.** Ça
> ferait même perdre : la mise en page du PDF (titres, numérotation) sert à
> reconstruire la structure, et un copier-coller la détruit.

Convertit n'importe quel format en **Markdown**. Ce n'est pas cosmétique :
les titres `#` sont le signal dont l'étape suivante se sert pour couper au bon
endroit.

| Format | Outil | Particularité |
| --- | --- | --- |
| PDF | `pypdf` | Structure reconstruite : « Chapitre 5 : … » et « 9. Titre : » redeviennent des titres. Sommaire et numéros de page supprimés. |
| DOCX | `python-docx` | Les styles Word « Titre 1/2/3 » deviennent `#`, `##`, `###` |
| MD | — | Tel quel : le fichier porte déjà sa syntaxe |
| TXT | — | Même reconstruction de titres que pour un PDF |
| Images | ❌ | OCR pas encore fait — un PDF scanné est refusé avec un message clair |

**Mesuré sur une fiche de révision BTS SIO de 1,3 Mo :**

| | Avant reconstruction | Après |
| --- | ---: | ---: |
| Fragments avec un vrai titre | 0 / 211 | **182 / 182** |
| Caractères indexés | 174 053 | 141 058 |

Les 33 000 caractères en moins sont du sommaire et des numéros de page :
du bruit qui polluait l'index sans rien apporter.

**Ce qui résiste encore :** les tableaux d'un PDF perdent leur structure et
deviennent une suite de mots. Une liste de verbes irréguliers en trois
colonnes ressort en « knew known connaître lay laid laid poser ». C'est
lisible par l'IA mais peu exploitable — pour ce type de contenu, un fichier
Markdown écrit à la main donne un bien meilleur résultat.

### ② Découpage — `services/rag/splitter.py`

**L'étape la plus sous-estimée.** La recherche renvoie des *fragments*, et
c'est le fragment brut qui part dans le prompt. Un mauvais découpage produit
des extraits amputés, l'IA répond à côté, et on accuse le modèle.

Trois niveaux, du signal le plus fort au plus faible :

1. **Aux titres** — une section de cours est une unité de sens.
2. **Aux paragraphes** — si la section dépasse 1200 caractères.
3. **Aux phrases** — si un paragraphe seul dépasse déjà la limite.

**Le chevauchement (150 caractères)** : chaque fragment reprend la fin du
précédent. Sans lui, une phrase qui tombe pile sur une frontière devient
introuvable.

Chaque fragment garde son **fil d'Ariane** : `Chapitre 3 > 3.2 Les jointures`.
Ce titre est réinjecté dans le prompt, ce qui permet à l'IA de sourcer sa
réponse.

### ③ Vectorisation — `services/rag/embeddings.py`

Un *embedding* transforme un texte en liste de nombres où **la proximité
géométrique traduit la proximité de sens**. « clé étrangère » et
« FOREIGN KEY » finissent voisins alors qu'ils ne partagent aucun caractère —
ce qu'une recherche par mots-clés ne saura jamais faire.

Trois fournisseurs interchangeables, choisis par `EMBEDDING_PROVIDER` :

| Valeur | Coût | Qualité | Quand |
| --- | --- | --- | --- |
| `fastembed` ⭐ | **gratuit, local** | bonne | Défaut. Modèle de ~130 Mo téléchargé au 1er usage puis mis en cache |
| `openai` | payant | excellente | Si tu veux le maximum |
| `hash` | gratuit | médiocre | Repli hors ligne, sac de mots — pour tester la plomberie |

> ⚠️ **Piège vécu :** le nom du modèle doit figurer dans
> `TextEmbedding.list_supported_models()` de fastembed. Sinon le code retombe
> **silencieusement** sur `hash` et la qualité s'effondre (score 0.32 au lieu
> de 0.54 sur la même requête). Vérifie toujours sur `/api/v1/ai/status`.

Modèle actuel : `paraphrase-multilingual-MiniLM-L12-v2`, **384 dimensions**,
multilingue — indispensable, tes cours sont en français.

### ④ Double stockage — le point important

| Où | Quoi | Pourquoi |
| --- | --- | --- |
| **Qdrant** | les 384 nombres | Seul capable de chercher « le plus proche » dans un espace à 384 dimensions, vite |
| **PostgreSQL** | le texte du fragment | Source de vérité, sauvegardable, lisible en SQL |

Le pont entre les deux est `DocumentChunk.point_id` (un UUID).

**La conséquence pratique :** si Qdrant est perdu, rien n'est perdu. Tout se
ré-indexe depuis PostgreSQL sans relire les fichiers d'origine :

```bash
curl -X POST http://localhost:8000/api/v1/documents/<id>/reindex \
  -H "Authorization: Bearer <ton-token>"
```

### ⑤ Recherche — `services/rag/qdrant.py`

Quatre collections, une par nature de contenu :

| Collection | Contenu | Intention de recherche |
| --- | --- | --- |
| `revisio_course` | tes cours | « explique-moi les jointures » |
| `revisio_exam` | BTS blancs, annales | « ça tombe souvent à l'examen ? » |
| `revisio_error` | tes erreurs passées | « je refais souvent cette faute ? » |
| `revisio_note` | notes perso | — |

Distance **cosinus** : on compare des *directions*, pas des longueurs.
Chaque point porte `user_id` dans son payload, et **toute recherche est
filtrée dessus** — avec un index, sinon ça devient un scan complet.

### ⑥⑦ Contexte et génération — `pipeline.py` + `ai/service.py`

`build_context()` assemble les extraits numérotés et sourcés :

```
[1] (Cours SQL — Chapitre 3 > 3.2 Les jointures)
La jointure interne ne conserve que les lignes...

---

[2] (BTS blanc 2024 — Exercice 2)
...
```

Puis `ask()` envoie ça au modèle avec la consigne de citer `[1]`, `[2]`.
**Une IA qui cite ses sources est une IA qu'on peut prendre en défaut, donc
en qui on peut avoir confiance.**

---

## 4. Vérifier que ça marche

```bash
curl http://localhost:8000/api/v1/ai/status -H "Authorization: Bearer <token>"
```

Ce que tu veux voir :

```json
{
  "embedder": "fastembed:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
  "embedding_dim": 384,
  "qdrant_reachable": true
}
```

Si `embedder` vaut `"hash"` → le modèle n'a pas pu se charger, regarde les
logs (`docker compose logs backend | grep fastembed`).

---

## 5. Où tournent les données aujourd'hui

**En local, dans le conteneur `revisio-qdrant` du Compose.** Rien à
configurer, rien à payer, aucune limite. Les vecteurs vivent dans le volume
Docker `revisio_qdrant_data` et survivent aux redémarrages.

```bash
docker compose ps qdrant          # état du conteneur
```

Le tableau de bord web est ouvert sur http://localhost:6333/dashboard — tu
peux y voir tes collections et inspecter les points un par un.

> **Et Qdrant Cloud ?** Utile seulement le jour du déploiement sur un VPS, ou
> si tu veux tes données accessibles depuis plusieurs machines. Ça demandera
> de rendre `QDRANT_URL` configurable dans `docker-compose.yml` (il est
> aujourd'hui forcé sur le service local) et de relancer un `reindex`. Rien
> d'urgent tant que tu développes ici.

---

## 6. Ce qui manque encore

| Manque | Impact |
| --- | --- |
| **OCR** | Les cours photographiés ou scannés sont refusés |
| **Recherche hybride** (sémantique + mots-clés) | Un code d'erreur exact ou un nom de fonction se trouve mieux en littéral |
| **Reranking** | Un second modèle qui reclasse les 20 premiers résultats améliore nettement la précision |
| **Ingestion asynchrone** | Un gros PDF bloque la requête HTTP pendant tout le traitement |
