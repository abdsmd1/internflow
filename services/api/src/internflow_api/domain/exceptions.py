"""Exceptions métier.

Elles expriment des violations de règles métier, sans rien savoir de HTTP :
c'est la couche présentation qui les traduit en codes de statut.
"""


class DomainError(Exception):
    """Classe de base de toutes les erreurs métier."""


class InvalidValueError(DomainError):
    """Une valeur ne respecte pas les invariants du domaine."""


class InternNotFoundError(DomainError):
    def __init__(self, intern_id: object) -> None:
        super().__init__(f"Aucun stagiaire avec l'identifiant {intern_id}.")
        self.intern_id = intern_id


class EmailAlreadyUsedError(DomainError):
    def __init__(self, email: str) -> None:
        super().__init__(f"L'adresse {email} est déjà utilisée par un autre stagiaire.")
        self.email = email
