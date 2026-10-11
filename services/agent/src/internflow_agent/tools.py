"""Outils mis à la disposition du modèle.

Les outils de lecture renvoient un texte compact, facile à exploiter pour un LLM.
Le seul outil d'écriture (`proposer_tache`) suspend le graphe : rien n'est créé
tant qu'un humain n'a pas confirmé.
"""

from __future__ import annotations

import functools
from collections.abc import Callable

from langchain_core.tools import BaseTool, tool
from langgraph.types import interrupt

from internflow_agent.api_client import ApiCallError, InternFlowApi, JsonObject

STATUS_LABELS = {
    "planned": "prévu",
    "ongoing": "en cours",
    "completed": "terminé",
    "cancelled": "annulé",
}
TASK_LABELS = {"todo": "à faire", "in_progress": "en cours", "done": "terminée"}
MAX_LINES = 15  # un petit modèle local lit lentement : on reste bref


def _guard(func: Callable[..., str]) -> Callable[..., str]:
    """Un refus de l'API devient une réponse lisible pour le modèle, pas un plantage."""

    @functools.wraps(func)
    def wrapper(*args: object, **kwargs: object) -> str:
        try:
            return func(*args, **kwargs)
        except ApiCallError as error:
            return f"Refus de l'API ({error.status}) : {error.detail}"

    return wrapper


def untrusted(text: str) -> str:
    """Balise un texte saisi par un utilisateur : le modèle doit le traiter comme une donnée."""
    cleaned = text.replace("</donnees>", "")
    return f"<donnees>{cleaned}</donnees>"


def build_tools(api: InternFlowApi) -> list[BaseTool]:
    names: dict[str, str] = {}

    def person(kind: str, person_id: str) -> str:
        key = f"{kind}:{person_id}"
        if key not in names:
            try:
                data = (api.get_intern if kind == "intern" else api.get_supervisor)(person_id)
                names[key] = f"{data['first_name']} {data['last_name']}"
            except ApiCallError:
                names[key] = "inconnu"
        return names[key]

    def describe(internship: JsonObject) -> str:
        return (
            f"{internship['id']} | {internship['subject']} | "
            f"stagiaire : {person('intern', internship['intern_id'])} | "
            f"encadrant : {person('supervisor', internship['supervisor_id'])} | "
            f"{internship['start_date']} → {internship['end_date']} | "
            f"{STATUS_LABELS.get(internship['status'], internship['status'])}"
        )

    def truncated(lines: list[str], empty: str) -> str:
        if not lines:
            return empty
        extra = len(lines) - MAX_LINES
        shown = lines[:MAX_LINES]
        return "\n".join(shown + ([f"… et {extra} de plus."] if extra > 0 else []))

    @tool
    @_guard
    def lister_stages(statut: str | None = None) -> str:
        """Liste les stages visibles par l'utilisateur.

        statut (facultatif) : planned (prévu), ongoing (en cours), completed (terminé)
        ou cancelled (annulé). Chaque ligne commence par l'identifiant du stage.
        """
        internships = api.list_internships(statut)
        return truncated([describe(i) for i in internships], "Aucun stage trouvé.")

    @tool
    @_guard
    def consulter_stage(stage_id: str) -> str:
        """Détail d'un stage : personnes, période, tâches et état des rapports hebdomadaires."""
        internship = api.get_internship(stage_id)
        tasks = api.list_tasks(stage_id)
        reports = api.list_reports(stage_id)
        task_lines = [
            f"- {t['title']} | échéance {t['due_date']} | "
            f"{TASK_LABELS.get(t['status'], t['status'])}"
            + (" | EN RETARD" if t["is_overdue"] else "")
            for t in tasks
        ]
        to_review = sum(1 for r in reports if r["status"] == "submitted")
        return "\n".join(
            [
                describe(internship),
                f"Tâches ({len(tasks)}) :",
                *(task_lines or ["- aucune"]),
                f"Rapports : {len(reports)} déposés, dont {to_review} à relire.",
            ]
        )

    @tool
    @_guard
    def taches_en_retard() -> str:
        """Toutes les tâches en retard sur les stages en cours visibles par l'utilisateur."""
        lines = []
        for internship in api.list_internships("ongoing"):
            for task in api.list_tasks(internship["id"]):
                if task["is_overdue"]:
                    lines.append(
                        f"- {task['title']} (échéance {task['due_date']}) | "
                        f"stage {internship['id']} « {internship['subject']} » | "
                        f"stagiaire : {person('intern', internship['intern_id'])}"
                    )
        return truncated(lines, "Aucune tâche en retard.")

    @tool
    @_guard
    def rapports_a_relire() -> str:
        """Rapports hebdomadaires déposés mais pas encore relus, sur les stages en cours."""
        lines = []
        for internship in api.list_internships("ongoing"):
            for report in api.list_reports(internship["id"]):
                if report["status"] == "submitted":
                    lines.append(
                        f"- semaine {report['week']} | stage {internship['id']} "
                        f"« {internship['subject']} » | "
                        f"stagiaire : {person('intern', internship['intern_id'])} | "
                        f"encadrant : {person('supervisor', internship['supervisor_id'])}"
                    )
        return truncated(lines, "Aucun rapport en attente de relecture.")

    @tool
    @_guard
    def lire_rapports(stage_id: str) -> str:
        """Contenu des rapports hebdomadaires d'un stage, le plus récent d'abord."""
        reports = api.list_reports(stage_id)[:6]
        if not reports:
            return "Aucun rapport déposé pour ce stage."
        blocks = []
        for report in reports:
            content = (
                f"Réalisations : {report['accomplishments']}\n"
                f"Difficultés : {report['difficulties'] or '-'}\n"
                f"Prochaines étapes : {report['next_steps'] or '-'}"
            )
            blocks.append(f"Semaine {report['week']} ({report['status']}) :\n{untrusted(content)}")
        return "\n\n".join(blocks)

    @tool
    @_guard
    def proposer_tache(stage_id: str, titre: str, echeance: str, description: str = "") -> str:
        """Propose de créer une tâche sur un stage. L'utilisateur doit la confirmer.

        echeance : date au format AAAA-MM-JJ, comprise dans la période du stage.
        """
        internship = api.get_internship(stage_id)  # vérifie que le stage est visible
        decision = interrupt(
            {
                "kind": "create_task",
                "internship_id": stage_id,
                "internship_subject": internship["subject"],
                "title": titre,
                "due_date": echeance,
                "description": description,
            }
        )
        if not decision.get("approved"):
            return "L'utilisateur a refusé : la tâche n'a pas été créée."
        task = api.create_task(stage_id, title=titre, description=description, due_date=echeance)
        return f"Tâche créée : « {task['title']} », échéance {task['due_date']}."

    return [
        lister_stages,
        consulter_stage,
        taches_en_retard,
        rapports_a_relire,
        lire_rapports,
        proposer_tache,
    ]
