# 0011 — Assistant IA : LangGraph, droits de l'utilisateur et validation humaine

- **Statut :** Accepté
- **Date :** 2026-10-11

## Contexte

Les RH et les encadrants veulent poser des questions en langage naturel (« quelles
tâches sont en retard ? », « quels rapports dois-je relire ? ») et déléguer de
petites actions, comme confier une tâche. Un assistant fondé sur un LLM répond à ce
besoin, mais il introduit trois risques :

1. **Fuite de données** : l'assistant pourrait montrer ce que l'utilisateur ne doit
   pas voir.
2. **Action non voulue** : une réponse mal interprétée, ou une consigne cachée dans
   un rapport (*injection de prompt*), pourrait déclencher une écriture.
3. **Hallucination** : le modèle peut inventer un nom, une date, un chiffre.

## Décision

### Un service séparé, qui passe par l'API

`services/agent` est un service FastAPI distinct. Il n'a **aucun accès à la base** :
il appelle l'API InternFlow **avec le jeton de l'utilisateur** qui discute avec lui.

- L'assistant ne peut jamais voir ni faire plus que l'utilisateur : les règles RBAC
  de l'API (ADR 0007) s'appliquent sans être dupliquées.
- Une conversation appartient à son auteur ; un autre utilisateur obtient 404.

### LangGraph : modèle ↔ outils, avec point d'arrêt

```
START → agent ──(appel d'outil ?)──► tools ──► agent … ──► END
                                       └─ proposer_tache : interrupt() → décision humaine
```

- Six outils typés : cinq en lecture (stages, détail d'un stage, tâches en retard,
  rapports à relire, contenu des rapports) et **un seul en écriture**,
  `proposer_tache`.
- `proposer_tache` appelle `interrupt()` : le graphe s'arrête, l'interface affiche
  la proposition, et **rien n'est créé tant que l'utilisateur n'a pas confirmé**.
  Après confirmation, l'API vérifie encore les droits (un refus 403 est expliqué).
- Garde-fous : nombre d'étapes limité par message, messages de 2 000 caractères
  au plus, température 0.

### Défenses contre l'injection de prompt

- Les textes saisis par les utilisateurs (contenu des rapports) sont encadrés par
  `<donnees>…</donnees>` ; le message système interdit d'y suivre des instructions.
- Surtout : même trompé, le modèle ne peut que **proposer** une action. La
  validation humaine est la vraie protection, pas la consigne.

### Modèle : local ou API cloud, au choix

- **Ollama + `qwen2.5:3b`** : modèle libre, exécuté en local, gratuit, sans envoyer
  de données personnelles à un tiers. Il gère l'appel d'outils et le français.
  Le premier essai avec `qwen2.5:7b` sur un portable (Docker limité à 7,6 Go)
  dépassait 3 minutes par réponse : le modèle 3B est donc le défaut, le 7B une option.
- Réglages pour le processeur : modèle gardé en mémoire 30 min, chargé dès le
  démarrage du service, contexte de 4 096 jetons, réponses de 512 jetons au plus,
  résultats d'outils limités à 15 lignes.
- **API compatible OpenAI** (`INTERNFLOW_AGENT_LLM_PROVIDER=openai`), Groq par défaut :
  modèles open source hébergés (`openai/gpt-oss-120b`), offre gratuite avec une
  clé, réponses en une à deux secondes. C'est l'option retenue pour les démonstrations
  sur un portable. Contrepartie : les questions et les données consultées sortent du
  poste ; acceptable ici (données fictives), à remplacer par un modèle local ou un
  fournisseur sous contrat pour de vraies données personnelles.
- Le fournisseur se choisit par configuration, sans toucher au graphe ; la clé est
  obligatoire et vérifiée au démarrage.

### Qualité

- **Tests** avec un modèle scénarisé : on vérifie le code (outils, validation
  humaine, droits, erreurs), pas la créativité du modèle.
- **Évaluations** (`make eval-agent`) avec le vrai modèle sur un jeu de données
  fictif : bon outil choisi, action proposée et non exécutée, consigne cachée dans un
  rapport ignorée, pas d'invention. Score affiché, seuil optionnel.
- Le contrat OpenAPI de l'assistant est exporté et vérifié, comme celui de l'API ;
  le frontend en génère ses types.

## Alternatives envisagées

- **Agent avec un compte de service privilégié** : plus simple, mais il verrait tout
  et deviendrait une porte dérobée autour du RBAC.
- **Accès SQL direct pour le modèle (text-to-SQL)** : puissant, mais impossible à
  borner correctement (droits, données sensibles, requêtes coûteuses).
- **API d'un fournisseur cloud par défaut** : meilleures réponses, mais coût à
  l'usage et données envoyées à l'extérieur ; reste disponible en option.
- **Écriture directe sans confirmation** : plus fluide, mais une seule injection de
  prompt réussie suffirait à modifier les données.

## Conséquences

- ✅ L'assistant hérite des droits de l'utilisateur, sans règle d'accès en double.
- ✅ Aucune écriture sans accord explicite ; le parcours est testé de bout en bout.
- ⚠️ Conversations en mémoire (`InMemorySaver`) : perdues au redémarrage du service,
  et limitées à une seule instance. Un checkpointer PostgreSQL lèvera ces limites.
- ⚠️ Sur processeur, les réponses prennent de quelques secondes à plusieurs minutes ;
  Ollama installé directement sur Windows (avec la carte graphique) est bien plus
  rapide que dans Docker, et reste utilisable via `INTERNFLOW_AGENT_OLLAMA_URL`.
- ⚠️ Pas encore de RAG vectoriel (pgvector) : les rapports sont lus par l'outil
  `lire_rapports`, suffisant tant qu'on interroge un stage à la fois.
