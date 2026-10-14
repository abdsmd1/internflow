"""Découpage des rapports en passages à indexer."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from internflow_api.domain.internship import InternshipId
from internflow_api.domain.report import IsoWeek, ReportStatus, WeeklyReport
from internflow_api.domain.report_search import (
    PASSAGE_MAX_LENGTH,
    ReportSection,
    split_into_passages,
)

NOW = datetime(2026, 10, 9, 17, 0, tzinfo=UTC)


def report(**overrides: object) -> WeeklyReport:
    values: dict[str, object] = {
        "internship_id": InternshipId(uuid4()),
        "week": IsoWeek(2026, 41),
        "accomplishments": "Mise en place de l'API.",
        "submitted_at": NOW,
    }
    values.update(overrides)
    return WeeklyReport(**values)  # type: ignore[arg-type]


def test_one_passage_per_filled_section_and_empty_ones_are_skipped() -> None:
    passages = split_into_passages(report(difficulties="Accès VPN refusé."))
    assert [(p.section, p.position, p.content) for p in passages] == [
        (ReportSection.ACCOMPLISHMENTS, 0, "Mise en place de l'API."),
        (ReportSection.DIFFICULTIES, 0, "Accès VPN refusé."),
    ]


def test_passages_keep_the_report_context() -> None:
    source = report()
    [passage] = split_into_passages(source)
    assert passage.report_id == source.id
    assert passage.internship_id == source.internship_id
    assert passage.week == IsoWeek(2026, 41)


def test_the_supervisor_feedback_is_indexed_once_the_report_is_reviewed() -> None:
    reviewed = report(
        status=ReportStatus.REVIEWED, feedback="Documenter le schéma.", reviewed_at=NOW
    )
    sections = [p.section for p in split_into_passages(reviewed)]
    assert sections == [ReportSection.ACCOMPLISHMENTS, ReportSection.FEEDBACK]


def test_the_section_label_gives_context_to_the_model() -> None:
    [passage] = split_into_passages(report(accomplishments="Tests écrits."))
    assert passage.text_to_embed == "Réalisations : Tests écrits."


def test_long_text_is_split_on_sentence_boundaries() -> None:
    sentences = [
        f"Phrase numéro {i} qui décrit une tâche réalisée cette semaine." for i in range(30)
    ]
    passages = split_into_passages(report(accomplishments=" ".join(sentences)))

    assert len(passages) > 1
    assert all(len(p.content) <= PASSAGE_MAX_LENGTH for p in passages)
    assert [p.position for p in passages] == list(range(len(passages)))
    assert all(p.content.endswith(".") for p in passages)  # aucune phrase coupée
    assert " ".join(p.content for p in passages) == " ".join(sentences)  # rien de perdu


def test_short_sentences_are_grouped_and_lines_are_sentence_breaks() -> None:
    passages = split_into_passages(report(accomplishments="Lecture du code\nRéunion. Revue !"))
    assert [p.content for p in passages] == ["Lecture du code Réunion. Revue !"]


def test_a_sentence_longer_than_the_limit_is_cut_between_words() -> None:
    text = "mot " * 40
    passages = split_into_passages(report(accomplishments=text), max_length=50)
    assert all(len(p.content) <= 50 for p in passages)
    assert all(not p.content.startswith(" ") and "mo t" not in p.content for p in passages)
    assert " ".join(p.content for p in passages) == text.strip()


def test_a_word_longer_than_the_limit_is_cut_anyway() -> None:
    passages = split_into_passages(report(accomplishments="x" * 120), max_length=50)
    assert [len(p.content) for p in passages] == [50, 50, 20]
