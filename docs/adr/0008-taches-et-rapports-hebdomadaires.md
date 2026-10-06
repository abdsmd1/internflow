# 0008 — Tâches et rapports hebdomadaires

- **Statut :** Accepté
- **Date :** 2026-10-06

## Contexte

Le suivi d'un stage repose sur deux pratiques : l'encadrant **confie des tâches**,
le stagiaire **rend compte chaque semaine**. Ces données serviront aussi de
matière première aux phases suivantes : indicateurs calculés avec PySpark
(délais, retards, régularité des rapports) et agent IA (résumé des rapports,
alertes).

## Décision

### Tâches

- Rattachées à un stage, avec une **échéance comprise dans la période du stage**.
- Cycle de vie `todo → in_progress → done` (une tâche peut être terminée
  directement) ; `done` est définitif.
- La date de réalisation `completed_at` est **conservée** (cohérence garantie par
  une contrainte `CHECK`) : elle permettra de mesurer les délais réels.
- Le **retard** (`is_overdue`) n'est pas stocké : il dépend de la date du jour et
  est calculé à la lecture, ce qui évite une donnée qui se périme.
- Créées par l'encadrant du stage (ou un RH), avancées par le stagiaire, son
  encadrant ou un RH. Un stage terminé ou annulé **gèle** ses tâches.

### Rapports hebdomadaires

- Une semaine est identifiée selon la **norme ISO 8601** (`2026-W41`, du lundi au
  dimanche) : aucune ambiguïté au changement d'année (le 1er janvier 2027
  appartient à la semaine `2026-W53`).
- **Un rapport par stage et par semaine**, garanti par une contrainte `UNIQUE
  (internship_id, iso_year, iso_week)` en plus de la vérification applicative.
- Dépôt **réservé au stagiaire**, sur un stage **en cours**, pour une semaine
  incluse dans la période du stage et déjà commencée.
- Relecture par l'encadrant (ou un RH) avec un retour écrit : `submitted → reviewed`.
- Contenu structuré (réalisations, difficultés, prochaines étapes) plutôt qu'un
  texte libre : plus facile à analyser ensuite.

## Alternatives envisagées

- **Semaine identifiée par sa date de début** : fonctionne, mais rien n'empêche
  d'enregistrer un mardi ; la semaine ISO rend la règle impossible à contourner.
- **Statut `overdue` stocké en base** : nécessiterait une tâche planifiée pour le
  mettre à jour, et deviendrait faux entre deux exécutions.
- **Modification d'un rapport après dépôt** : écartée pour l'instant ; un rapport
  relu doit rester tel que l'encadrant l'a lu.

## Conséquences

- ✅ Données horodatées et structurées, prêtes pour les pipelines de la phase 3.
- ✅ Migration générée automatiquement (`alembic --autogenerate`) puis relue : un
  index redondant a été retiré.
- ⚠️ Pas encore de notification (rapport manquant, tâche en retard) : ce sera le
  rôle des traitements planifiés et de l'agent IA.
