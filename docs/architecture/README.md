# Architecture (modèle C4)

## Niveau 1 — Contexte

```mermaid
flowchart LR
    rh([Responsable RH])
    enc([Encadrant])
    stg([Stagiaire])
    sys[[InternFlow]]
    llm[(Fournisseur LLM)]
    mail[(Service e-mail)]

    rh -- gère candidatures, conventions --> sys
    enc -- suit tâches, évalue --> sys
    stg -- dépose rapports --> sys
    sys -- requêtes de l'agent IA --> llm
    sys -- notifications --> mail
```

## Niveau 2 — Conteneurs (cible)

```mermaid
flowchart TB
    front[Frontend React]
    api[API FastAPI<br/><i>services/api</i>]
    agent[Agent IA LangGraph<br/><i>services/agent</i>]
    db[(PostgreSQL + pgvector)]
    lake[(MinIO<br/>bronze / silver / gold)]
    spark[Jobs PySpark<br/><i>data/</i>]
    airflow[Airflow]

    front -->|HTTPS / JSON| api
    front -->|chat| agent
    agent -->|appelle l'API<br/>avec son propre rôle| api
    api --> db
    airflow -->|planifie| spark
    spark -->|lit / écrit| lake
    spark -->|extraction| db
    spark -->|scores de matching| api
```

| Conteneur | État |
|-----------|------|
| API FastAPI | ✅ Stagiaires, encadrants, stages, rôles, tâches et rapports hebdomadaires |
| PostgreSQL | ✅ Phase 1 |
| Jobs PySpark + MinIO + Airflow | ⏳ Phase 2 |
| Modèle de matching (MLlib + MLflow) | ⏳ Phase 3 |
| Agent IA | ⏳ Phase 4 |
| Frontend | ⏳ Phase 5 |

## Niveau 3 — Composants du service API

```mermaid
flowchart LR
    subgraph presentation
        routes[Routes v1] --> deps[Dépendances]
        errors[Erreurs RFC 9457]
        mw[Middleware X-Request-ID]
    end
    subgraph application
        uc[Cas d'usage<br/>stagiaires, encadrants,<br/>stages et leur cycle de vie]
    end
    subgraph domain
        ent[Intern, Supervisor, Internship<br/>Email, PersonName, DateRange]
        ports{{Ports<br/>Repositories, UnitOfWork, Clock}}
    end
    subgraph infrastructure
        sql[SqlAlchemyUnitOfWork]
        mem[InMemoryUnitOfWork]
        clk[SystemClock]
    end

    deps --> uc --> ent
    uc --> ports
    sql -. implémente .-> ports
    mem -. implémente .-> ports
    clk -. implémente .-> ports
```

Décision détaillée : [ADR 0002](../adr/0002-architecture-hexagonale.md).
