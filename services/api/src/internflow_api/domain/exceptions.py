"""Exceptions métier.

Elles expriment des violations de règles métier, sans rien savoir de HTTP.
Chaque exception porte :
- une **catégorie** (sa classe parente), que la présentation traduit en statut HTTP ;
- un **code** stable (`code`), utilisable par les clients (frontend, agent IA).
"""

from __future__ import annotations

from typing import ClassVar


class DomainError(Exception):
    """Classe de base de toutes les erreurs métier."""

    code: ClassVar[str] = "domain-error"


# ----------------------------------------------------------------- catégories
class InvalidValueError(DomainError):
    """Une valeur ne respecte pas les invariants du domaine."""

    code = "invalid-value"


class NotFoundError(DomainError):
    """L'élément demandé n'existe pas."""

    code = "not-found"


class BusinessRuleViolationError(DomainError):
    """L'action est valide en soi mais contredit l'état actuel du système."""

    code = "business-rule-violation"


class UnauthenticatedError(DomainError):
    """L'identité de l'appelant n'a pas pu être établie."""

    code = "unauthenticated"


class PermissionDeniedError(DomainError):
    """L'appelant est identifié mais n'a pas le droit d'effectuer cette action."""

    code = "permission-denied"

    def __init__(
        self, message: str = "Vous n'avez pas les droits pour effectuer cette action."
    ) -> None:
        super().__init__(message)


# -------------------------------------------------------------- introuvables
class InternNotFoundError(NotFoundError):
    code = "intern-not-found"

    def __init__(self, intern_id: object) -> None:
        super().__init__(f"Aucun stagiaire avec l'identifiant {intern_id}.")
        self.intern_id = intern_id


class SupervisorNotFoundError(NotFoundError):
    code = "supervisor-not-found"

    def __init__(self, supervisor_id: object) -> None:
        super().__init__(f"Aucun encadrant avec l'identifiant {supervisor_id}.")
        self.supervisor_id = supervisor_id


class TaskNotFoundError(NotFoundError):
    code = "task-not-found"

    def __init__(self, task_id: object) -> None:
        super().__init__(f"Aucune tâche avec l'identifiant {task_id}.")
        self.task_id = task_id


class ReportNotFoundError(NotFoundError):
    code = "report-not-found"

    def __init__(self, report_id: object) -> None:
        super().__init__(f"Aucun rapport avec l'identifiant {report_id}.")
        self.report_id = report_id


class InternshipNotFoundError(NotFoundError):
    code = "internship-not-found"

    def __init__(self, internship_id: object) -> None:
        super().__init__(f"Aucun stage avec l'identifiant {internship_id}.")
        self.internship_id = internship_id


# ------------------------------------------------------------- règles métier
class EmailAlreadyUsedError(BusinessRuleViolationError):
    code = "email-already-used"

    def __init__(self, email: str) -> None:
        super().__init__(f"L'adresse {email} est déjà utilisée.")
        self.email = email


class InternshipOverlapError(BusinessRuleViolationError):
    code = "internship-overlap"

    def __init__(self, intern_id: object) -> None:
        super().__init__(
            f"Le stagiaire {intern_id} a déjà un stage prévu ou en cours sur cette période."
        )
        self.intern_id = intern_id


class SupervisorCapacityExceededError(BusinessRuleViolationError):
    code = "supervisor-capacity-exceeded"

    def __init__(self, supervisor_id: object, max_interns: int) -> None:
        super().__init__(
            f"L'encadrant {supervisor_id} suit déjà {max_interns} stagiaire(s) sur cette "
            "période : capacité maximale atteinte."
        )
        self.supervisor_id = supervisor_id
        self.max_interns = max_interns


class InvalidStatusTransitionError(BusinessRuleViolationError):
    code = "invalid-status-transition"

    def __init__(self, current: str, action: str) -> None:
        super().__init__(f"Action « {action} » impossible au statut « {current} ».")
        self.current = current
        self.action = action


class InternshipNotStartableYetError(BusinessRuleViolationError):
    code = "internship-not-startable-yet"

    def __init__(self, start_date: object) -> None:
        super().__init__(f"Le stage ne peut pas démarrer avant sa date de début ({start_date}).")
        self.start_date = start_date


class InternshipClosedError(BusinessRuleViolationError):
    code = "internship-closed"

    def __init__(self, internship_id: object) -> None:
        super().__init__(f"Le stage {internship_id} est terminé ou annulé : il n'évolue plus.")
        self.internship_id = internship_id


class InternshipNotOngoingError(BusinessRuleViolationError):
    code = "internship-not-ongoing"

    def __init__(self, internship_id: object) -> None:
        super().__init__(
            f"Le stage {internship_id} n'est pas en cours : impossible de déposer un rapport."
        )
        self.internship_id = internship_id


class ReportAlreadySubmittedError(BusinessRuleViolationError):
    code = "report-already-submitted"

    def __init__(self, week: object) -> None:
        super().__init__(f"Un rapport a déjà été déposé pour la semaine {week}.")
        self.week = week


class AccountAlreadyLinkedError(BusinessRuleViolationError):
    code = "account-already-linked"

    def __init__(self, profile_id: object) -> None:
        super().__init__(f"Le profil {profile_id} possède déjà un compte utilisateur.")
        self.profile_id = profile_id


# ----------------------------------------------------------- authentification
class InvalidCredentialsError(UnauthenticatedError):
    code = "invalid-credentials"

    def __init__(self) -> None:
        # Message volontairement identique que l'e-mail existe ou non :
        # on ne révèle pas quels comptes existent.
        super().__init__("E-mail ou mot de passe incorrect.")


class InvalidTokenError(UnauthenticatedError):
    code = "invalid-token"

    def __init__(self) -> None:
        super().__init__("Jeton d'accès absent, invalide ou expiré.")


class WeakPasswordError(InvalidValueError):
    code = "weak-password"
