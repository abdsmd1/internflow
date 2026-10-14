"""Recherche sémantique dans les rapports hebdomadaires (RAG).

Un rapport est découpé en **passages** courts, chacun rattaché à sa section
(réalisations, difficultés…). Chaque passage est converti en vecteur
(« embedding ») : deux textes de sens proche ont des vecteurs proches, même
sans mot commun (« bloqué sur le déploiement » ≈ « problème avec Docker »).

Les passages sont courts car le modèle d'embeddings ne lit qu'environ 128
jetons (≈ 500 caractères) : au-delà, la fin du texte serait ignorée.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from internflow_api.domain.internship import InternshipId
from internflow_api.domain.report import IsoWeek, ReportId, WeeklyReport

PASSAGE_MAX_LENGTH = 500
_SENTENCE_END = re.compile(r"(?<=[.!?;])\s+|\n+")


class ReportSection(StrEnum):
    ACCOMPLISHMENTS = "accomplishments"
    DIFFICULTIES = "difficulties"
    NEXT_STEPS = "next_steps"
    FEEDBACK = "feedback"

    @property
    def label(self) -> str:
        return _SECTION_LABELS[self]


_SECTION_LABELS = {
    ReportSection.ACCOMPLISHMENTS: "Réalisations",
    ReportSection.DIFFICULTIES: "Difficultés",
    ReportSection.NEXT_STEPS: "Prochaines étapes",
    ReportSection.FEEDBACK: "Retour de l'encadrant",
}


@dataclass(frozen=True, slots=True)
class ReportPassage:
    report_id: ReportId
    internship_id: InternshipId
    week: IsoWeek
    section: ReportSection
    position: int  # rang du passage dans sa section (0, 1, 2…)
    content: str

    @property
    def text_to_embed(self) -> str:
        # Le nom de la section donne du contexte au modèle : « Difficultés : … ».
        return f"{self.section.label} : {self.content}"


@dataclass(frozen=True, slots=True)
class SearchHit:
    passage: ReportPassage
    score: float  # similarité cosinus : 1 = même sens, 0 = sans rapport


def _split_text(text: str, max_length: int) -> list[str]:
    """Regroupe des phrases entières en morceaux d'au plus `max_length` caractères.

    Une phrase plus longue que la limite est coupée entre deux mots.
    """
    pieces: list[str] = []
    for raw_sentence in _SENTENCE_END.split(text):
        sentence = raw_sentence.strip()
        while len(sentence) > max_length:
            cut = sentence.rfind(" ", 0, max_length + 1)
            cut = cut if cut > 0 else max_length
            pieces.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if sentence:
            pieces.append(sentence)

    chunks: list[str] = []
    for piece in pieces:
        if chunks and len(chunks[-1]) + 1 + len(piece) <= max_length:
            chunks[-1] = f"{chunks[-1]} {piece}"
        else:
            chunks.append(piece)
    return chunks


def split_into_passages(
    report: WeeklyReport, *, max_length: int = PASSAGE_MAX_LENGTH
) -> list[ReportPassage]:
    """Découpe un rapport en passages prêts à être indexés (sections vides ignorées)."""
    sections = {
        ReportSection.ACCOMPLISHMENTS: report.accomplishments,
        ReportSection.DIFFICULTIES: report.difficulties,
        ReportSection.NEXT_STEPS: report.next_steps,
        ReportSection.FEEDBACK: report.feedback or "",
    }
    return [
        ReportPassage(
            report_id=report.id,
            internship_id=report.internship_id,
            week=report.week,
            section=section,
            position=position,
            content=chunk,
        )
        for section, text in sections.items()
        for position, chunk in enumerate(_split_text(text, max_length))
    ]
