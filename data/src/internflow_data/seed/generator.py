"""Génère un historique réaliste de stages en rejouant le temps.

Principe : pour chaque stage, on avance une horloge simulée (planification,
démarrage, tâches, rapports hebdomadaires, relectures, clôture) et l'on passe
**par les entités du domaine**. Une donnée impossible pour l'API (stage trop long,
rapport en double, semaine future, tâche hors période…) est donc impossible ici.

Le générateur est déterministe : même `seed` et même `today` → mêmes données.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta

from faker import Faker

from internflow_api.domain.intern import Intern
from internflow_api.domain.internship import DateRange, Internship
from internflow_api.domain.ports.unit_of_work import UnitOfWork
from internflow_api.domain.report import IsoWeek, WeeklyReport
from internflow_api.domain.supervisor import Supervisor
from internflow_api.domain.task import Task
from internflow_api.domain.user import Role, User
from internflow_api.domain.value_objects import Email, PersonName, StudyLevel

EMAIL_DOMAIN = "exemple.ma"  # domaine fictif réservé aux données générées
# Empreinte volontairement invalide : les comptes générés ne permettent aucune
# connexion (on ne crée jamais de mot de passe par défaut).
DISABLED_PASSWORD_HASH = "!compte-genere-sans-connexion"  # noqa: S105 (pas un secret)

DEPARTMENTS = ("Data & IA", "Développement web", "Cloud & DevOps", "Cybersécurité", "Mobile")
SCHOOLS = (
    "ENSA Oujda",
    "ENSIAS Rabat",
    "EMI Rabat",
    "INPT Rabat",
    "ENSA Tanger",
    "FST Fès",
    "EST Oujda",
    "ENSAM Casablanca",
)
STUDY_LEVEL_WEIGHTS: dict[StudyLevel, int] = {
    StudyLevel.INGENIEUR: 45,
    StudyLevel.MASTER_2: 20,
    StudyLevel.MASTER_1: 10,
    StudyLevel.LICENCE: 15,
    StudyLevel.BAC_PLUS_2: 10,
}
SUBJECTS = (
    "Agent IA de suivi des stagiaires",
    "Pipeline de données avec PySpark",
    "Tableau de bord RH",
    "API de gestion des conventions",
    "Détection d'anomalies dans les logs",
    "Application mobile de pointage",
    "Migration vers Kubernetes",
    "Audit de sécurité d'une application web",
    "Moteur de recommandation de formations",
    "Chatbot d'assistance interne",
)
TASK_TITLES = (
    "Rédiger le cahier des charges",
    "Modéliser la base de données",
    "Mettre en place l'environnement de développement",
    "Développer le module d'authentification",
    "Écrire les tests unitaires",
    "Préparer la démonstration intermédiaire",
    "Documenter l'architecture",
    "Optimiser les requêtes",
    "Intégrer la CI/CD",
    "Rédiger le rapport de stage",
)
ACCOMPLISHMENTS = (
    "Avancement sur le module principal et revue de code avec l'encadrant.",
    "Mise en place des tests et correction de plusieurs anomalies.",
    "Étude des besoins et rédaction de la documentation technique.",
    "Développement d'une nouvelle fonctionnalité et démonstration.",
    "Analyse des données et préparation des premiers indicateurs.",
)
DIFFICULTIES = (
    "",
    "",
    "Accès à l'environnement de test.",
    "Données incomplètes.",
    "Montée en compétence sur l'outil.",
)
FEEDBACKS = (
    "Bon travail, continuer ainsi.",
    "Penser à mieux documenter les choix techniques.",
    "Avancement correct, attention aux délais.",
    "Très bonne semaine.",
)

MIN_DURATION_DAYS = 56
MAX_DURATION_DAYS = 182  # < 183 jours : durée maximale autorisée par le domaine


@dataclass(frozen=True, slots=True)
class SeedConfig:
    supervisors: int = 20
    interns: int = 200
    seed: int = 42
    # Fenêtre de dates de début des stages, relative à `today`.
    earliest_start_days_ago: int = 300
    latest_start_days_ahead: int = 30


@dataclass(slots=True)
class GeneratedData:
    supervisors: list[Supervisor] = field(default_factory=list)
    interns: list[Intern] = field(default_factory=list)
    users: list[User] = field(default_factory=list)
    internships: list[Internship] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)
    reports: list[WeeklyReport] = field(default_factory=list)


def _at(day: date, hour: int = 9) -> datetime:
    return datetime.combine(day, time(hour), tzinfo=UTC)


class HistoryGenerator:
    def __init__(self, config: SeedConfig, today: date) -> None:
        self._config = config
        self._today = today
        self._rng = random.Random(config.seed)  # noqa: S311 (données fictives, pas de cryptographie)
        self._faker = Faker("fr_FR")
        self._faker.seed_instance(config.seed)
        self._data = GeneratedData()
        # Charge de chaque encadrant : périodes des stages actifs qui lui sont confiés.
        self._load: dict[Supervisor, list[DateRange]] = {}

    def generate(self) -> GeneratedData:
        self._create_supervisors()
        for index in range(self._config.interns):
            intern = self._create_intern(index)
            self._simulate_internship(intern)
        return self._data

    # ------------------------------------------------------------ référentiel
    def _email(self, index: int, kind: str) -> Email:
        local = self._faker.unique.user_name()
        return Email(f"{kind}.{local}.{self._config.seed}{index}@{EMAIL_DOMAIN}".lower())

    def _create_supervisors(self) -> None:
        for index in range(self._config.supervisors):
            first, last = self._faker.first_name(), self._faker.last_name()
            created = _at(self._today - timedelta(days=self._config.earliest_start_days_ago + 30))
            supervisor = Supervisor(
                name=PersonName(first, last),
                email=self._email(index, "enc"),
                department=self._rng.choice(DEPARTMENTS),
                max_interns=self._rng.randint(3, 6),
                created_at=created,
            )
            self._data.supervisors.append(supervisor)
            self._data.users.append(
                User(
                    email=supervisor.email,
                    password_hash=DISABLED_PASSWORD_HASH,
                    role=Role.SUPERVISOR,
                    supervisor_id=supervisor.id,
                    created_at=created,
                )
            )
            self._load[supervisor] = []

    def _create_intern(self, index: int) -> Intern:
        first, last = self._faker.first_name(), self._faker.last_name()
        intern = Intern(
            name=PersonName(first, last),
            email=self._email(index, "stg"),
            school=self._rng.choice(SCHOOLS),
            study_level=self._rng.choices(
                list(STUDY_LEVEL_WEIGHTS), weights=list(STUDY_LEVEL_WEIGHTS.values())
            )[0],
            created_at=_at(self._today - timedelta(days=self._config.earliest_start_days_ago + 20)),
        )
        self._data.interns.append(intern)
        return intern

    def _pick_supervisor(self, period: DateRange) -> Supervisor | None:
        """Un encadrant qui a encore de la capacité sur la période (règle du domaine)."""
        candidates = list(self._load)
        self._rng.shuffle(candidates)
        for supervisor in candidates:
            busy = sum(1 for other in self._load[supervisor] if other.overlaps(period))
            if busy < supervisor.max_interns:
                self._load[supervisor].append(period)
                return supervisor
        return None

    # -------------------------------------------------------------- simulation
    def _simulate_internship(self, intern: Intern) -> None:
        offset = self._rng.randint(
            -self._config.earliest_start_days_ago, self._config.latest_start_days_ahead
        )
        start = self._today + timedelta(days=offset)
        start -= timedelta(days=start.weekday())  # les stages commencent un lundi
        period = DateRange(
            start, start + timedelta(days=self._rng.randint(MIN_DURATION_DAYS, MAX_DURATION_DAYS))
        )
        supervisor = self._pick_supervisor(period)
        if supervisor is None:  # tous les encadrants sont pleins : stagiaire sans stage
            return

        internship = Internship.plan(
            intern_id=intern.id,
            supervisor_id=supervisor.id,
            subject=self._rng.choice(SUBJECTS),
            period=period,
            now=_at(start - timedelta(days=self._rng.randint(10, 30))),
        )
        self._data.internships.append(internship)
        if start > self._today:
            return  # stage encore à venir : il reste « planned »

        internship.start(today=start)
        cancel_on = self._cancellation_date(period)
        last_active_day = min(period.end, self._today, cancel_on or period.end)
        account = self._account_of(supervisor)
        diligence = self._rng.uniform(0.55, 1.0)  # régularité propre à chaque stagiaire

        self._simulate_tasks(internship, account, last_active_day, diligence)
        self._simulate_reports(internship, last_active_day, diligence)

        if cancel_on is not None:
            internship.cancel()
        elif period.end < self._today:
            internship.complete()

    def _cancellation_date(self, period: DateRange) -> date | None:
        if period.start >= self._today or self._rng.random() > 0.05:  # noqa: PLR2004
            return None
        latest = min(period.end, self._today)
        return period.start + timedelta(
            days=self._rng.randint(7, max(7, (latest - period.start).days))
        )

    def _account_of(self, supervisor: Supervisor) -> User:
        return next(u for u in self._data.users if u.supervisor_id == supervisor.id)

    def _simulate_tasks(
        self, internship: Internship, author: User, last_active_day: date, diligence: float
    ) -> None:
        period = internship.period
        count = max(2, period.days // 14)
        horizon = min(period.end, self._today + timedelta(days=30))
        for _ in range(count):
            due = period.start + timedelta(
                days=self._rng.randint(7, max(7, (horizon - period.start).days))
            )
            due = min(due, period.end)
            created_on = max(period.start, due - timedelta(days=self._rng.randint(5, 14)))
            if created_on > last_active_day:
                continue
            task = Task.create(
                internship=internship,
                title=self._rng.choice(TASK_TITLES),
                due_date=due,
                created_by=author.id,
                now=_at(created_on, 10),
            )
            delay = round(self._rng.gauss(1.5 - 3 * diligence, 3))
            done_on = max(created_on, due + timedelta(days=max(-7, min(14, delay))))
            if done_on <= last_active_day and self._rng.random() < 0.6 + 0.4 * diligence:
                if self._rng.random() < 0.7:  # noqa: PLR2004
                    task.start()
                task.complete(_at(done_on, 17))
            elif self._rng.random() < 0.5:  # noqa: PLR2004 — tâche commencée, pas encore finie
                task.start()
            self._data.tasks.append(task)

    def _simulate_reports(
        self, internship: Internship, last_active_day: date, diligence: float
    ) -> None:
        week = IsoWeek.of(internship.period.start)
        # On s'arrête à la dernière semaine terminée : la semaine en cours reste ouverte.
        last_week = IsoWeek.of(min(last_active_day, self._today - timedelta(days=7)))
        while week <= last_week:
            if self._rng.random() < diligence:
                submitted = _at(week.monday + timedelta(days=4), 17)  # vendredi soir
                report = WeeklyReport.submit(
                    internship=internship,
                    week=week,
                    accomplishments=self._rng.choice(ACCOMPLISHMENTS),
                    difficulties=self._rng.choice(DIFFICULTIES),
                    next_steps="Poursuivre selon le planning.",
                    now=submitted,
                )
                reviewed = submitted + timedelta(days=self._rng.randint(1, 6))
                if reviewed.date() <= self._today and self._rng.random() < 0.8:  # noqa: PLR2004
                    report.review(self._rng.choice(FEEDBACKS), reviewed)
                self._data.reports.append(report)
            week = IsoWeek.of(week.monday + timedelta(days=7))


def persist(data: GeneratedData, uow: UnitOfWork) -> None:
    """Enregistre tout dans une seule transaction : tout ou rien."""
    with uow:
        for supervisor in data.supervisors:
            uow.supervisors.add(supervisor)
        for intern in data.interns:
            uow.interns.add(intern)
        for user in data.users:
            uow.users.add(user)
        for internship in data.internships:
            uow.internships.add(internship)
        for task in data.tasks:
            uow.tasks.add(task)
        for report in data.reports:
            uow.reports.add(report)
        uow.commit()
