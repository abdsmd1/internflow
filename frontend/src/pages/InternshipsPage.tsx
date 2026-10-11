import { useState, type SubmitEvent } from "react";
import { Link } from "react-router";

import { useInterns, useInternships, usePlanInternship, useSupervisors } from "../api/queries";
import type { InternshipStatus } from "../api/types";
import { ErrorAlert } from "../components/ErrorAlert";
import { Pagination } from "../components/Pagination";
import { InternName, SupervisorName } from "../components/PersonName";
import { InternshipStatusBadge } from "../components/StatusBadge";
import { useMe } from "../auth/useAuth";
import { INTERNSHIP_STATUS_LABELS, formatPeriod, fullName, plural } from "../lib/format";
import { readForm } from "../lib/forms";

const FILTERS: (InternshipStatus | null)[] = [null, "planned", "ongoing", "completed", "cancelled"];

export function InternshipsPage() {
  const me = useMe();
  const [status, setStatus] = useState<InternshipStatus | null>(null);
  const [offset, setOffset] = useState(0);
  const { data, error, isPending } = useInternships(status, offset);

  return (
    <section>
      <header className="page-header">
        <h1>{me.role === "intern" ? "Mon stage" : "Stages"}</h1>
        {data && <p className="page-header__count">{plural(data.total, "stage", "stages")}</p>}
      </header>

      {me.role === "hr" && <PlanInternshipForm />}

      <div className="filters" role="group" aria-label="Filtrer par statut">
        {FILTERS.map((value) => (
          <button
            key={value ?? "all"}
            type="button"
            className="chip"
            aria-pressed={status === value}
            onClick={() => {
              setStatus(value);
              setOffset(0);
            }}
          >
            {value ? INTERNSHIP_STATUS_LABELS[value] : "Tous"}
          </button>
        ))}
      </div>

      <ErrorAlert error={error} />
      {isPending && <p className="loading">Chargement…</p>}
      {data && (
        <>
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Sujet</th>
                <th scope="col">Stagiaire</th>
                <th scope="col">Encadrant</th>
                <th scope="col">Période</th>
                <th scope="col">Statut</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((internship) => (
                <tr key={internship.id}>
                  <td>
                    <Link to={`/stages/${internship.id}`}>{internship.subject}</Link>
                  </td>
                  <td>
                    <InternName id={internship.intern_id} />
                  </td>
                  <td>
                    <SupervisorName id={internship.supervisor_id} />
                  </td>
                  <td className="nowrap">
                    {formatPeriod(internship.start_date, internship.end_date)}
                  </td>
                  <td>
                    <InternshipStatusBadge status={internship.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.items.length === 0 && (
            <p className="empty">
              {status ? "Aucun stage avec ce statut." : "Aucun stage pour l'instant."}
            </p>
          )}
          <Pagination {...data} onChange={setOffset} />
        </>
      )}
    </section>
  );
}

function PlanInternshipForm() {
  const plan = usePlanInternship();
  // Listes de choix : les 100 premiers suffisent pour un service RH.
  const interns = useInterns(0);
  const supervisors = useSupervisors(0, 100);

  function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const field = readForm(formElement);
    plan.mutate(
      {
        intern_id: field("intern_id"),
        supervisor_id: field("supervisor_id"),
        subject: field("subject"),
        start_date: field("start_date"),
        end_date: field("end_date"),
      },
      {
        onSuccess: () => {
          formElement.reset();
        },
      },
    );
  }

  return (
    <details className="panel">
      <summary>Planifier un stage</summary>
      <form className="form form--grid" onSubmit={handleSubmit}>
        <label className="form__wide">
          Sujet
          <input name="subject" required maxLength={200} />
        </label>
        <label>
          Stagiaire
          <select name="intern_id" required defaultValue="">
            <option value="" disabled>
              Choisir un stagiaire
            </option>
            {interns.data?.items.map((intern) => (
              <option key={intern.id} value={intern.id}>
                {fullName(intern)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Encadrant
          <select name="supervisor_id" required defaultValue="">
            <option value="" disabled>
              Choisir un encadrant
            </option>
            {supervisors.data?.items.map((supervisor) => (
              <option key={supervisor.id} value={supervisor.id}>
                {fullName(supervisor)} ({supervisor.department})
              </option>
            ))}
          </select>
        </label>
        <label>
          Début
          <input name="start_date" type="date" required />
        </label>
        <label>
          Fin
          <input name="end_date" type="date" required />
        </label>
        <div className="form__actions">
          <ErrorAlert error={plan.error} />
          {plan.isSuccess && <p role="status">Stage planifié.</p>}
          <button type="submit" className="button" disabled={plan.isPending}>
            Planifier le stage
          </button>
        </div>
      </form>
    </details>
  );
}
