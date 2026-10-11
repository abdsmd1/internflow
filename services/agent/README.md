# internflow-agent

Assistant IA d'InternFlow : LangGraph + Ollama. Il répond aux questions sur les
stages, les tâches et les rapports, et **propose** des tâches que l'utilisateur
confirme. Les choix sont expliqués dans
l'[ADR 0011](../../docs/adr/0011-agent-ia-langgraph.md).

## Lancer avec Docker

```bash
docker compose --profile ai up -d    # Ollama + téléchargement du modèle + assistant
```

Le premier lancement télécharge le modèle (environ 5 Go). Ouvrez ensuite
http://localhost:8080, page **Assistant**.

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
| `proposer_tache` | **écriture** : s'arrête et attend la confirmation de l'utilisateur |

## Configuration (préfixe `INTERNFLOW_AGENT_`)

| Variable | Défaut | Rôle |
|----------|--------|------|
| `API_URL` | `http://localhost:8000` | API InternFlow |
| `LLM_PROVIDER` | `ollama` | `ollama` ou `anthropic` (dépendance optionnelle) |
| `LLM_MODEL` | `qwen2.5:7b` | modèle utilisé |
| `OLLAMA_URL` | `http://localhost:11434` | serveur Ollama |
| `MAX_STEPS` | `8` | allers-retours modèle ↔ outils par message |

## Tests et évaluations

```bash
uv run pytest                    # modèle simulé : rapide, sans Ollama
make eval-agent                  # vrai modèle, jeu de données fictif, score affiché
```
