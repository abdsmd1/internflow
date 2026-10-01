# 0004 — PostgreSQL et migrations Alembic

- **Statut :** Accepté
- **Date :** 2026-10-01

## Contexte

Les données des stagiaires sont relationnelles (stagiaire ↔ stage ↔ encadrant ↔
évaluations) et exigent des garanties fortes (unicité, transactions). L'agent IA
aura besoin d'une recherche vectorielle sur les CV.

## Décision

- **PostgreSQL 16** comme base transactionnelle ; l'extension **pgvector** sera
  ajoutée pour le RAG plutôt qu'une base vectorielle séparée.
- Le schéma évolue **uniquement** par des migrations **Alembic** versionnées,
  relues en PR et **réversibles** (vérifié par le test « escalier » upgrade →
  downgrade → upgrade).
- Les contraintes d'intégrité vivent aussi en base (ex. `uq_interns_email`) :
  la vérification applicative ne suffit pas face aux requêtes concurrentes.
- Les dates sont stockées en `TIMESTAMP WITH TIME ZONE` et manipulées en UTC.

## Alternatives envisagées

- **MongoDB** : souple, mais les relations et contraintes seraient à gérer à la main.
- **`Base.metadata.create_all()`** : pratique pour un prototype, mais aucun historique
  ni retour arrière possible sur une base qui contient des données.

## Conséquences

- ✅ Une seule base à opérer pour les données métier et les embeddings.
- ⚠️ Chaque changement de modèle demande une migration (`make migration m="…"`).
