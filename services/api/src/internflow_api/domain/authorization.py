"""Règles d'autorisation (RBAC + propriété des ressources).

| Action                              | RH | Encadrant          | Stagiaire        |
|-------------------------------------|----|--------------------|------------------|
| Créer stagiaire / encadrant / stage | ✅ | ❌                 | ❌               |
| Créer un compte utilisateur         | ✅ | ❌                 | ❌               |
| Lister / consulter les stagiaires   | ✅ | ✅                 | lui-même         |
| Lister / consulter les encadrants   | ✅ | ✅                 | ✅               |
| Lister / consulter les stages       | ✅ | les siens          | les siens        |
| Démarrer / terminer un stage        | ✅ | les siens          | ❌               |
| Annuler un stage                    | ✅ | ❌                 | ❌               |

Choix de sécurité : une ressource que l'appelant n'a pas le droit de **voir** est
signalée comme introuvable (404) plutôt qu'interdite (403), pour ne pas révéler
son existence. Le 403 est réservé aux actions refusées sur une ressource visible.
"""

from __future__ import annotations

from dataclasses import replace

from internflow_api.domain.exceptions import (
    InternNotFoundError,
    InternshipNotFoundError,
    PermissionDeniedError,
)
from internflow_api.domain.intern import InternId
from internflow_api.domain.internship import Internship
from internflow_api.domain.ports.repositories import InternshipFilter
from internflow_api.domain.user import Principal, Role


def require_role(actor: Principal, *allowed: Role) -> None:
    if actor.role not in allowed:
        raise PermissionDeniedError


def ensure_can_view_intern(actor: Principal, intern_id: InternId) -> None:
    if actor.role is Role.INTERN and actor.intern_id != intern_id:
        raise InternNotFoundError(intern_id)


def can_view_internship(actor: Principal, internship: Internship) -> bool:
    match actor.role:
        case Role.HR:
            return True
        case Role.SUPERVISOR:
            return internship.supervisor_id == actor.supervisor_id
        case Role.INTERN:
            return internship.intern_id == actor.intern_id


def ensure_can_view_internship(actor: Principal, internship: Internship) -> None:
    if not can_view_internship(actor, internship):
        raise InternshipNotFoundError(internship.id)


def scope_internship_filter(actor: Principal, criteria: InternshipFilter) -> InternshipFilter:
    """Restreint une recherche aux stages que l'appelant a le droit de voir."""
    match actor.role:
        case Role.HR:
            return criteria
        case Role.SUPERVISOR:
            return replace(criteria, supervisor_id=actor.supervisor_id)
        case Role.INTERN:
            return replace(criteria, intern_id=actor.intern_id)


def ensure_can_progress_internship(actor: Principal, internship: Internship) -> None:
    """Démarrer / terminer : RH, ou l'encadrant du stage."""
    ensure_can_view_internship(actor, internship)
    require_role(actor, Role.HR, Role.SUPERVISOR)


def ensure_can_cancel_internship(actor: Principal, internship: Internship) -> None:
    """Annuler : décision réservée aux RH."""
    ensure_can_view_internship(actor, internship)
    require_role(actor, Role.HR)
