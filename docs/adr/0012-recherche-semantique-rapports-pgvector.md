# 0012 — Recherche sémantique dans les rapports (RAG avec pgvector)

- **Statut :** Accepté
- **Date :** 2026-10-14

## Contexte

L'assistant (ADR 0011) lisait les rapports d'**un** stage à la fois (`lire_rapports`).
Des questions courantes restaient sans réponse fiable : « Qui a eu des problèmes avec
Docker ? », « Quels stagiaires sont bloqués sur les accès ? ». Il faudrait lire tous
les rapports de tous les stages, ce qui dépasse le contexte d'un LLM.

De plus, une recherche par mots-clés échoue dès que les mots diffèrent : « les
conteneurs ne démarrent pas » ne contient pas le mot « Docker ».

Contraintes : les droits d'accès (ADR 0007) doivent s'appliquer à la recherche
comme partout ailleurs, et le poste de développement n'a pas de carte graphique.

## Décision

### Chaîne RAG

```
rapport déposé / relu ──► découpage en passages ──► embedding ──► report_passages (pgvector)
question ──► embedding ──► GET /api/v1/reports/search ──► passages + sources ──► LLM
```

1. **Découpage** (domaine, `split_into_passages`) : un passage par section (réalisations,
   difficultés, prochaines étapes, retour de l'encadrant), coupé en morceaux d'au
   plus 500 caractères sur les fins de phrase. Le modèle ne lit que 128 jetons :
   au-delà, la fin du texte serait ignorée.
2. **Embeddings** : modèle **local** `paraphrase-multilingual-MiniLM-L12-v2` (384
   dimensions, ~50 langues dont le français), exécuté sur CPU par **FastEmbed / ONNX
   Runtime** derrière le port `TextEmbedder`.
3. **Stockage** : **pgvector** dans la base PostgreSQL existante, table
   `report_passages` (clé naturelle : rapport, section, rang ; suppression en cascade).
4. **Recherche** : route `GET /api/v1/reports/search?q=…`, distance cosinus, seuil de
   pertinence réglable (`INTERNFLOW_SEARCH_MIN_SCORE`, 0,3 par défaut).
5. **Génération** : l'outil `rechercher_dans_rapports` de l'agent appelle cette route
   **avec le jeton de l'utilisateur** et transmet au LLM chaque passage avec sa source
   (stagiaire, semaine, section), balisé `<donnees>` comme tout texte saisi.

### La recherche est dans l'API, pas dans l'agent

L'agent n'a pas accès à la base : la recherche passe par l'API, qui applique le même
filtre de droits que la liste des stages (`scope_internship_filter`), **dans la requête
SQL**. Un encadrant ne trouve que les passages des stages qu'il encadre ; un passage
hors périmètre n'est jamais lu. La recherche sert aussi bien l'interface que l'agent.

### Indexation dans la même transaction

Déposer un rapport ou le relire recalcule ses passages **dans la même transaction** :
l'index reflète toujours les données. Si le modèle est indisponible, l'action métier
réussit quand même (le rapport compte plus que sa recherche), un avertissement est
journalisé et `reindex-reports` rattrape l'index. La même commande indexe les données
importées par le générateur, qui écrit sans passer par les cas d'usage.

### Recherche exacte, sans index approché

Aucun index HNSW pour l'instant. Avec un index approché, PostgreSQL prend d'abord les
~40 voisins les plus proches **tous stages confondus**, puis applique le filtre de
droits : un encadrant de 3 stagiaires sur 200 risquerait de ne rien trouver. La
recherche exacte respecte les filtres sans perte, et quelques dizaines de milliers de
passages se parcourent en quelques millisecondes.

### Modèle embarqué dans l'image

Le modèle (~220 Mo) est téléchargé **au build** dans une étape dédiée, puis lu hors
ligne (`HF_HUB_OFFLINE=1`) depuis un système de fichiers en lecture seule. La CI le
vérifie : conteneur sans réseau, et contrôle que le modèle rapproche bien deux phrases
de même sens en français.

## Alternatives envisagées

- **API d'embeddings (OpenAI, Mistral, Gemini)** : rien à héberger, mais les rapports
  partiraient chez un tiers, il faut une clé de plus, et Groq n'en propose pas.
- **Embeddings via Ollama** : déjà présent en option, mais un service de plus à faire
  tourner pour une fonction centrale de l'API.
- **Base vectorielle dédiée (Qdrant, Chroma)** : un service et une copie des données
  en plus, avec des droits à resynchroniser. pgvector garde données, droits et
  vecteurs dans la même transaction.
- **Recherche plein texte PostgreSQL** : précise sur les mots exacts, aveugle aux
  synonymes. Une recherche **hybride** (plein texte + vecteurs) est une évolution possible.
- **Modèle anglais (`bge-small-en`)** : plus léger, mais médiocre sur des rapports en français.

## Conséquences

- ✅ L'assistant répond aux questions transversales et cite ses sources.
- ✅ Aucun texte ne quitte le serveur pour la recherche ; aucune clé, aucun quota.
- ✅ Droits appliqués en SQL, testés sur un vrai PostgreSQL avec pgvector.
- ⚠️ Image de l'API plus lourde (modèle et ONNX Runtime, ~350 Mo de plus) ; ~300 Mo de
  mémoire une fois le modèle chargé (au démarrage, en arrière-plan).
- ⚠️ La taille des vecteurs (384) est figée dans le schéma : changer pour un modèle de
  taille différente demande une migration puis `reindex-reports`.
- ⚠️ Le seuil de pertinence (0,3) est un point de départ, à ajuster sur des cas réels.
- ⚠️ Au-delà d'environ 100 000 passages : ajouter un index HNSW avec le parcours
  itératif de pgvector 0.8 (`hnsw.iterative_scan`), qui préserve les filtres.
