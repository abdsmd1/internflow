# 0003 — Monorepo géré avec uv

- **Statut :** Accepté
- **Date :** 2026-10-01

## Contexte

Le projet comprendra plusieurs services Python (API, agent IA, jobs PySpark) qui
partagent des conventions de qualité, mais dont les dépendances divergent
fortement (PySpark est lourd et inutile pour l'API).

## Décision

- Un seul dépôt Git (monorepo) avec un dossier par service : `services/api`,
  puis `services/agent` et `data/`.
- **uv workspace** à la racine : un seul `uv.lock` garantit des versions
  identiques en local, en CI et dans les images Docker.
- Chaque service a son propre `pyproject.toml` ; Ruff est configuré à la racine.

## Alternatives envisagées

- **Un dépôt par service** : isolation forte, mais coordination pénible pour un
  projet mené par une seule personne.
- **Poetry / pip-tools** : fonctionnels, mais uv est nettement plus rapide et gère
  aussi l'installation de Python.

## Conséquences

- ✅ `make check` vérifie tout le projet en une commande.
- ⚠️ Les images Docker doivent être construites depuis la racine (contexte de build).
