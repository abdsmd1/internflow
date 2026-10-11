/**
 * Fausse API (MSW) : elle intercepte les vraies requêtes HTTP du client, avec les
 * mêmes URL et formats d'erreur (RFC 9457) que l'API FastAPI.
 */
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import type { Me, Role } from "../api/types";
import * as fx from "./fixtures";

const BASE = "http://localhost:3000/api/v1";

export const ACCOUNTS: Record<string, Me> = {
  "rh@exemple.ma": { user_id: "u-hr", role: "hr", intern_id: null, supervisor_id: null },
  "karim@exemple.ma": {
    user_id: "u-sup",
    role: "supervisor",
    intern_id: null,
    supervisor_id: fx.supervisor.id,
  },
  "sara@exemple.ma": {
    user_id: "u-int",
    role: "intern",
    intern_id: fx.intern.id,
    supervisor_id: null,
  },
};

export function tokenFor(role: Role): string {
  return `jeton-${role}`;
}

function problem(status: number, detail: string) {
  return HttpResponse.json(
    { type: "about:blank", title: "Erreur", status, detail },
    { status, headers: { "Content-Type": "application/problem+json" } },
  );
}

function roleOf(request: Request): Role | null {
  const token = request.headers.get("Authorization")?.replace("Bearer ", "");
  const match = Object.values(ACCOUNTS).find((me) => tokenFor(me.role) === token);
  return match?.role ?? null;
}

const initial = () => ({
  internships: [fx.planned, fx.ongoing],
  tasks: [fx.task],
  reports: [fx.report],
  interns: [fx.intern],
  supervisors: [fx.supervisor],
});

export let db = initial();

/** Corps reçus par la fausse API, pour vérifier ce que l'interface a envoyé. */
export const received: { path: string; body: unknown }[] = [];

export function resetDatabase(): void {
  db = initial();
  received.length = 0;
}

function page<T>(items: T[]) {
  return { items, total: items.length, offset: 0, limit: 20 };
}

export const handlers = [
  http.post(`${BASE}/auth/token`, async ({ request }) => {
    const form = new URLSearchParams(await request.text());
    const me = ACCOUNTS[form.get("username") ?? ""];
    if (!me || form.get("password") !== fx.PASSWORD) {
      return problem(401, "E-mail ou mot de passe incorrect.");
    }
    return HttpResponse.json({
      access_token: tokenFor(me.role),
      token_type: "bearer",
      expires_in: 1800,
    });
  }),

  // Toutes les autres routes exigent un jeton valide.
  http.all(`${BASE}/*`, ({ request }) => {
    if (!roleOf(request)) return problem(401, "Jeton absent, invalide ou expiré.");
    return undefined; // laisse passer vers le gestionnaire suivant
  }),

  http.get(`${BASE}/auth/me`, ({ request }) => {
    const role = roleOf(request);
    return HttpResponse.json(Object.values(ACCOUNTS).find((me) => me.role === role));
  }),

  http.get(`${BASE}/internships`, ({ request }) => {
    const status = new URL(request.url).searchParams.get("status");
    return HttpResponse.json(page(db.internships.filter((i) => !status || i.status === status)));
  }),
  http.post(`${BASE}/internships`, async ({ request }) => {
    const body = await request.json();
    received.push({ path: "internships", body });
    return HttpResponse.json({ ...fx.planned, id: "nouveau" }, { status: 201 });
  }),
  http.get(`${BASE}/internships/:id`, ({ params }) => {
    const found = db.internships.find((i) => i.id === params.id);
    return found ? HttpResponse.json(found) : problem(404, "Stage introuvable.");
  }),
  http.post(`${BASE}/internships/:id/:action`, ({ params }) => {
    if (!["start", "complete", "cancel"].includes(params.action as string)) return undefined;
    const found = db.internships.find((i) => i.id === params.id);
    if (!found) return problem(404, "Stage introuvable.");
    const status = { start: "ongoing", complete: "completed", cancel: "cancelled" } as const;
    const updated = { ...found, status: status[params.action as keyof typeof status] };
    db.internships = db.internships.map((i) => (i.id === found.id ? updated : i));
    return HttpResponse.json(updated);
  }),

  http.get(`${BASE}/internships/:id/tasks`, () => HttpResponse.json(db.tasks)),
  http.post(`${BASE}/internships/:id/tasks`, async ({ request }) => {
    const body = (await request.json()) as { title: string; description: string; due_date: string };
    received.push({ path: "tasks", body });
    const created = { ...fx.task, id: "tache-2", ...body };
    db.tasks = [...db.tasks, created];
    return HttpResponse.json(created, { status: 201 });
  }),
  http.post(`${BASE}/tasks/:id/:action`, ({ params }) => {
    const status = params.action === "start" ? "in_progress" : "done";
    db.tasks = db.tasks.map((t) => (t.id === params.id ? { ...t, status } : t));
    return HttpResponse.json(db.tasks.find((t) => t.id === params.id));
  }),

  http.get(`${BASE}/internships/:id/reports`, () => HttpResponse.json(db.reports)),
  http.post(`${BASE}/internships/:id/reports`, async ({ request }) => {
    const body = (await request.json()) as { week: string; accomplishments: string };
    received.push({ path: "reports", body });
    if (db.reports.some((r) => r.week === body.week)) {
      return problem(409, "Un rapport existe déjà pour cette semaine.");
    }
    const created = { ...fx.report, id: "rapport-2", ...body };
    db.reports = [created, ...db.reports];
    return HttpResponse.json(created, { status: 201 });
  }),
  http.post(`${BASE}/reports/:id/review`, async ({ params, request }) => {
    const { feedback } = (await request.json()) as { feedback: string };
    db.reports = db.reports.map((r) =>
      r.id === params.id ? { ...r, status: "reviewed" as const, feedback } : r,
    );
    return HttpResponse.json(db.reports.find((r) => r.id === params.id));
  }),

  http.get(`${BASE}/interns`, () => HttpResponse.json(page(db.interns))),
  http.post(`${BASE}/interns`, async ({ request }) => {
    const body = (await request.json()) as typeof fx.intern;
    received.push({ path: "interns", body });
    if (db.interns.some((i) => i.email === body.email)) {
      return problem(409, "Un stagiaire avec cet e-mail existe déjà.");
    }
    db.interns = [...db.interns, { ...body, id: "stagiaire-2", created_at: fx.intern.created_at }];
    return HttpResponse.json(db.interns.at(-1), { status: 201 });
  }),
  http.get(`${BASE}/interns/:id`, ({ params }) => {
    const found = db.interns.find((i) => i.id === params.id);
    return found ? HttpResponse.json(found) : problem(404, "Stagiaire introuvable.");
  }),

  http.get(`${BASE}/supervisors`, () => HttpResponse.json(page(db.supervisors))),
  http.post(`${BASE}/supervisors`, async ({ request }) => {
    const body = (await request.json()) as typeof fx.supervisor;
    received.push({ path: "supervisors", body });
    db.supervisors = [...db.supervisors, { ...body, id: "encadrant-2", created_at: "" }];
    return HttpResponse.json(db.supervisors.at(-1), { status: 201 });
  }),
  http.get(`${BASE}/supervisors/:id`, ({ params }) => {
    const found = db.supervisors.find((s) => s.id === params.id);
    return found ? HttpResponse.json(found) : problem(404, "Encadrant introuvable.");
  }),
];

export const server = setupServer(...handlers);
