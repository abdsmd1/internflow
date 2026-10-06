"""Jobs : lecture → transformations pures → contrôles qualité → écriture.

Organisation du data lake (architecture « médaillon ») :

    lake/bronze/<table>/ingestion_date=AAAA-MM-JJ/   copie brute (minimisée) de PostgreSQL
    lake/silver/<jeu>/                               données typées, propres, pseudonymisées
    lake/gold/<indicateur>/as_of=AAAA-MM-JJ/         indicateurs, un instantané par date

Chaque job est idempotent : le relancer pour la même date remplace exactement
les mêmes partitions, sans doublon.
"""
