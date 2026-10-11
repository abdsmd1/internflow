import type { Intern, Internship, Report, Supervisor, Task } from "../api/types";

export const PASSWORD = "phrase-de-passe-de-test";

export const intern: Intern = {
  id: "11111111-1111-4111-8111-111111111111",
  first_name: "Sara",
  last_name: "El Amrani",
  email: "sara@exemple.ma",
  school: "ENSA Oujda",
  study_level: "ingenieur",
  created_at: "2026-09-01T09:00:00Z",
};

export const supervisor: Supervisor = {
  id: "22222222-2222-4222-8222-222222222222",
  first_name: "Karim",
  last_name: "Benali",
  email: "karim@exemple.ma",
  department: "Data & IA",
  max_interns: 3,
  created_at: "2026-09-01T09:00:00Z",
};

export const ongoing: Internship = {
  id: "33333333-3333-4333-8333-333333333333",
  intern_id: intern.id,
  supervisor_id: supervisor.id,
  subject: "Agent IA de suivi des stagiaires",
  start_date: "2026-09-28",
  end_date: "2026-12-18",
  duration_days: 82,
  status: "ongoing",
  created_at: "2026-09-01T09:00:00Z",
};

export const planned: Internship = {
  ...ongoing,
  id: "44444444-4444-4444-8444-444444444444",
  subject: "Tableau de bord RH",
  start_date: "2026-11-02",
  end_date: "2027-02-26",
  duration_days: 117,
  status: "planned",
};

export const task: Task = {
  id: "55555555-5555-4555-8555-555555555555",
  internship_id: ongoing.id,
  title: "Modéliser la base de données",
  description: "Schéma et migrations",
  due_date: "2026-10-09",
  status: "todo",
  is_overdue: false,
  created_by: supervisor.id,
  created_at: "2026-09-29T09:00:00Z",
  completed_at: null,
};

export const report: Report = {
  id: "66666666-6666-4666-8666-666666666666",
  internship_id: ongoing.id,
  week: "2026-W40",
  week_start: "2026-09-28",
  week_end: "2026-10-04",
  accomplishments: "Mise en place du projet",
  difficulties: "",
  next_steps: "Modéliser la base",
  status: "submitted",
  feedback: null,
  submitted_at: "2026-10-02T17:00:00Z",
  reviewed_at: null,
};
