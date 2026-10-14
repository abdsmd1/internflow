# internflow-agent

Assistant IA d'InternFlow : LangGraph + Ollama. Il répond aux questions sur les
stages, les tâches et les rapports, et **propose** des tâches que l'utilisateur
confirme. Les choix sont expliqués dans
l'[ADR 0011](../../docs/adr/0011-agent-ia-langgraph.md).

## Lancer avec Docker

**Avec une API cloud (recommandé sur un portable)** : créez une clé gratuite sur
https://console.groq.com/keys, renseignez-la dans `.env`
(`INTERNFLOW_AGENT_LLM_PROVIDER=openai`, `INTERNFLOW_AGENT_LLM_API_KEY=…`), puis :

```bash
docker compose --profile ai up -d
```

**Avec un modèle local** (`INTERNFLOW_AGENT_LLM_PROVIDER=ollama`) : le premier
lancement télécharge le modèle (environ 2 Go).

```bash
docker compose --profile ai --profile ollama up -d
```

Ouvrez ensuite http://localhost:8080, page **Assistant**.

## Fonctionnement

```
Interface ──► nginx ──► agent ──(jeton de l'utilisateur)──► API InternFlow
                          │
                          └──► Ollama (modèle de langage local)
```

| Outil | Rôle |
|-------|------|
| `lister_stages` | stages visibles, filtrables par statut |
| `consulter_stage` | personnes, tâches, état des rapports d'un stage |
| `taches_en_retard` | tâches en retard sur les stages en cours |
| `rapports_a_relire` | rapports déposés mais pas encore relus |
| `lire_rapports` | contenu des rapports d'un stage (balisé comme donnée non fiable) |
| `rechercher_dans_rapports` | **RAG** : passages de rapports proches de la question, tous stages visibles, avec leur source |
| `proposer_tache` | **écriture** : s'arrête et attend la confirmation de l'utilisateur |

## Configuration (préfixe `INTERNFLOW_AGENT_`)

| Variable | Défaut | Rôle |
|----------|--------|------|
| `API_URL` | `http://localhost:8000` | API InternFlow |
| `LLM_PROVIDER` | `ollama` | `ollama`, `openai` (toute API compatible, Groq par défaut) ou `anthropic` |
| `LLM_API_KEY` | — | clé de l'API cloud (obligatoire avec `openai`) |
| `OPENAI_BASE_URL` | `https://api.groq.com/openai/v1` | adresse de l'API compatible OpenAI |
| `LLM_MODEL` | `qwen2.5:3b` | modèle utilisé (`qwen2.5:7b` : meilleur, plus lourd) |
| `LLM_KEEP_ALIVE` | `30m` | durée pendant laquelle Ollama garde le modèle en mémoire |
| `LLM_CONTEXT_TOKENS` | `4096` | taille du contexte envoyé au modèle |
| `OLLAMA_URL` | `http://localhost:11434` | serveur Ollama |
| `MAX_STEPS` | `8` | allers-retours modèle ↔ outils par message |

## Tests et évaluations

```bash
uv run pytest                    # modèle simulé : rapide, sans Ollama
make eval-agent                  # vrai modèle, jeu de données fictif, score affiché
```
