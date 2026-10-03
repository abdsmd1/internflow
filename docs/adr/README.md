# Architecture Decision Records (ADR)

Un ADR documente **une** décision d'architecture : le contexte, le choix fait,
les alternatives écartées et les conséquences. Il n'est jamais modifié après
acceptation : si la décision change, on écrit un nouvel ADR qui remplace l'ancien.

| N° | Décision | Statut |
|----|----------|--------|
| [0001](0001-enregistrer-les-decisions.md) | Enregistrer les décisions d'architecture | Accepté |
| [0002](0002-architecture-hexagonale.md) | Architecture hexagonale pour le service API | Accepté |
| [0003](0003-monorepo-uv.md) | Monorepo géré avec uv | Accepté |
| [0004](0004-postgresql-et-alembic.md) | PostgreSQL et migrations Alembic | Accepté |
| [0005](0005-format-erreurs-rfc9457.md) | Format d'erreur RFC 9457 | Accepté |
| [0006](0006-stages-machine-a-etats-et-integrite.md) | Stages : machine à états et garanties d'intégrité | Accepté |

Modèle pour un nouvel ADR : copier [`template.md`](template.md).
