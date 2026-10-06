# 0009 — Pipeline PySpark en architecture médaillon

- **Statut :** Accepté
- **Date :** 2026-10-06

## Contexte

Les RH et les encadrants veulent des **indicateurs** : taux de tâches rendues à
l'heure, régularité des rapports hebdomadaires, charge de chaque encadrant,
activité semaine par semaine. Les calculer à la volée dans l'API alourdirait la
base transactionnelle et mélangerait deux besoins différents (gérer / analyser).

Ces indicateurs serviront aussi de contexte à l'agent IA (phase 5) : ils doivent
être **fiables, reproductibles et sans données personnelles**.

## Décision

### Un pipeline batch PySpark en trois couches (« médaillon »)

```
PostgreSQL ──JDBC──► bronze ──► silver ──► gold
                     copie brute  nettoyé,     indicateurs
                     datée        pseudonymisé  datés (as_of)
```

| Couche | Contenu | Partitionnement |
|--------|---------|-----------------|
| `bronze/<table>` | copie fidèle des colonnes utiles | `ingestion_date=` |
| `silver/<jeu>` | dédoublonné, typé, clés pseudonymisées, colonnes dérivées | remplacé à chaque exécution |
| `gold/<indicateur>` | `internship_kpis`, `supervisor_workload`, `weekly_activity` | `as_of=` |

Le stockage est en **Parquet** sur un dossier local (`data/lake/`). Le passage à
un stockage objet (MinIO/S3) ne changera que le chemin.

### Protection des données dès la conception (RGPD)

- **Minimisation :** l'extraction utilise des `SELECT` explicites ; noms,
  e-mails, sujets, contenus des rapports et des tâches ne quittent **jamais**
  PostgreSQL.
- **Pseudonymisation :** les identifiants sont remplacés dès silver par
  `SHA-256(sel ‖ id)`. Le sel est un **secret obligatoire** (16 caractères
  minimum, sans valeur par défaut) : sans lui, impossible de relier une clé à
  une personne.

### Fiabilité

- **Contrats de schéma explicites** (`StructType`) : une colonne manquante fait
  échouer l'extraction immédiatement, au lieu de corrompre la suite.
- **Contrôles qualité bloquants** à chaque couche (non-nullité, unicité,
  valeurs autorisées, bornes, cohérence `done ⇔ completed_date`). En cas d'échec,
  rien n'est publié et la commande sort avec le code 2.
- **Idempotence :** réexécuter le pipeline pour la même date remplace la même
  partition (`partitionOverwriteMode=dynamic`) ; aucune ligne n'est dupliquée.
- **Transformations pures** (`DataFrame → DataFrame`), testées sur de petits jeux
  de données construits à la main, dont chaque résultat se vérifie de tête.
- **Date de référence injectée** (`--date`) : un indicateur comme « tâche en
  retard » dépend du jour de calcul ; il est donc reproductible.
- Fuseau horaire de Spark fixé à **UTC**, comme l'API.

### Données de démonstration

La commande `seed` simule un historique réaliste **en passant par les entités du
domaine** : chaque règle métier (capacité des encadrants, durée maximale d'un
stage, un rapport par semaine…) est respectée par construction. La génération
est déterministe (graine) et n'utilise que des données fictives (Faker, domaine
`exemple.ma`, comptes sans mot de passe utilisable).

### Images Docker et vulnérabilités

L'image `data` embarque Java 21 et les jars fournis par PySpark. Ces jars ne
peuvent pas être mis à jour un par un : ils suivent les versions de Spark. La CI
bloque donc sur les vulnérabilités du système et des paquets Python, et produit
un **rapport séparé, non bloquant**, pour les jars de Spark.

## Alternatives envisagées

- **Pandas :** suffisant pour ce volume, mais l'objectif est de pratiquer un
  outil qui passe à l'échelle ; les mêmes transformations tourneraient sur un
  cluster sans modification.
- **Delta Lake / Iceberg :** transactions ACID et historique des versions, mais
  une dépendance de plus ; à reconsidérer avec MinIO.
- **Vues SQL dans PostgreSQL :** simple, mais charge la base transactionnelle et
  n'offre ni historique (`as_of`) ni pseudonymisation.
- **Hachage sans sel :** les identifiants sont des UUID devinables par
  rapprochement ; un sel secret empêche de recalculer les clés.

## Conséquences

- ✅ Indicateurs vérifiés : sur 155 stages, recalcul indépendant en SQL identique
  pour 10 indicateurs.
- ✅ Aucune donnée personnelle dans silver et gold (vérifié par un test
  d'intégration).
- ⚠️ Java est nécessaire pour exécuter les tests du pipeline : en local sous
  Windows, on passe par l'image Docker.
- ⚠️ Pas encore d'orchestration : le pipeline se lance à la demande. Airflow
  arrivera avec MinIO.
- ⚠️ Changer le sel rend les nouvelles clés impossibles à relier aux anciennes
  (c'est voulu) : les instantanés gold antérieurs ne sont plus comparables.
