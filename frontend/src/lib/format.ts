import type { InternshipStatus, Role, StudyLevel, TaskStatus } from "../api/types";

const dateFormat = new Intl.DateTimeFormat("fr-FR", {
  day: "numeric",
  month: "short",
  year: "numeric",
});
const shortDate = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short" });

/** Les dates de l'API (« 2026-10-05 ») sont des jours, sans fuseau horaire. */
export function parseDay(value: string): Date {
  const [year, month, day] = value.slice(0, 10).split("-").map(Number);
  return new Date(Date.UTC(year ?? 1970, (month ?? 1) - 1, day ?? 1));
}

export function formatDay(value: string): string {
  return dateFormat.format(parseDay(value));
}

export function formatShortDay(value: string): string {
  return shortDate.format(parseDay(value));
}

export function formatPeriod(start: string, end: string): string {
  return `${formatDay(start)} – ${formatDay(end)}`;
}

export const ROLE_LABELS: Record<Role, string> = {
  hr: "Ressources humaines",
  supervisor: "Encadrant",
  intern: "Stagiaire",
};

export const INTERNSHIP_STATUS_LABELS: Record<InternshipStatus, string> = {
  planned: "Prévu",
  ongoing: "En cours",
  completed: "Terminé",
  cancelled: "Annulé",
};

export const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  todo: "À faire",
  in_progress: "En cours",
  done: "Terminée",
};

export const STUDY_LEVEL_LABELS: Record<StudyLevel, string> = {
  "bac+2": "Bac+2",
  licence: "Licence",
  master_1: "Master 1",
  master_2: "Master 2",
  ingenieur: "Cycle ingénieur",
  doctorat: "Doctorat",
};

/** « 1 rapport déposé », « 3 rapports déposés ». */
export function plural(count: number, singular: string, pluralForm: string): string {
  return `${count} ${count > 1 ? pluralForm : singular}`;
}

export function fullName(person: { first_name: string; last_name: string }): string {
  return `${person.first_name} ${person.last_name}`;
}
