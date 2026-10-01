"""Ports : interfaces dont le domaine et les cas d'usage ont besoin.

Ce sont des `Protocol` (typage structurel) : l'infrastructure fournit les
implémentations (PostgreSQL, mémoire…) sans que le domaine les connaisse.
C'est le « D » de SOLID : inversion des dépendances.
"""
