# 0002 — Architecture hexagonale pour le service API

- **Statut :** Accepté
- **Date :** 2026-10-01

## Contexte

Les règles métier (unicité de l'e-mail, validité d'un stagiaire, plus tard les
conventions et évaluations) doivent rester stables alors que la technique évolue :
changement de base, ajout de l'agent IA comme nouveau client, jobs Spark.
Elles doivent aussi être testables en quelques millisecondes.

## Décision

Le service API suit une architecture hexagonale (ports & adapters) en quatre couches :

```
presentation ──▶ application ──▶ domain ◀── infrastructure
   (FastAPI)       (cas d'usage)   (règles)    (PostgreSQL, horloge…)
```

- **domain** : entités, value objects, exceptions et *ports* (`Protocol`). Aucun framework.
- **application** : un cas d'usage par action métier, qui orchestre le domaine via les ports.
- **infrastructure** : implémentations des ports (SQLAlchemy, mémoire, horloge système).
- **presentation** : routes HTTP, DTO Pydantic, traduction des erreurs.
- **main.py** est l'unique *composition root* où les adaptateurs sont assemblés.

La règle de dépendance est **vérifiée automatiquement** par Ruff (règle `TID251`,
fichiers `ruff.toml` dans `domain/` et `application/`).

Patterns associés : Repository, Unit of Work, Data Mapper, injection de dépendances.

## Alternatives envisagées

- **Architecture en couches classique (routes → services → modèles ORM)** : plus
  rapide au départ, mais le métier se retrouve couplé à SQLAlchemy et aux routes.
- **Modèles SQLAlchemy utilisés comme entités** : moins de code, mais le schéma de
  la base dicte le modèle métier et les tests unitaires exigent une base.

## Conséquences

- ✅ Domaine et cas d'usage testés sans base ni serveur (tests rapides).
- ✅ L'agent IA pourra réutiliser les mêmes cas d'usage via l'API.
- ⚠️ Plus de fichiers et un mapping explicite entité ↔ enregistrement SQL.
