# 0001 — Enregistrer les décisions d'architecture

- **Statut :** Accepté
- **Date :** 2026-10-01

## Contexte

InternFlow combine plusieurs technologies (API, PySpark, agent IA). Sans trace
écrite, on oublie pourquoi un choix a été fait, et on le remet en question sans
connaître ses raisons.

## Décision

Chaque décision d'architecture significative est consignée dans `docs/adr/` au
format de Michael Nygard (contexte, décision, alternatives, conséquences).

## Conséquences

- Les nouveaux contributeurs comprennent l'historique des choix.
- Une décision se révise par un nouvel ADR, jamais en réécrivant l'ancien.
