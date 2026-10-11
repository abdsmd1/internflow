import { useState, type SubmitEvent } from "react";

import { useReviewReport, useSubmitReport } from "../../api/queries";
import type { Internship, Report } from "../../api/types";
import { ErrorAlert } from "../../components/ErrorAlert";
import { formatShortDay, parseDay } from "../../lib/format";
import { isoWeekOf, todayUtc, weeksBetween } from "../../lib/isoWeek";
import { readForm } from "../../lib/forms";

export function ReportsSection({
  internship,
  reports,
  canSubmit,
  canReview,
}: {
  internship: Internship;
  reports: Report[];
  canSubmit: boolean;
  canReview: boolean;
}) {
  return (
    <section className="section" aria-labelledby="reports-title">
      <h2 id="reports-title">Comptes rendus</h2>
      {canSubmit && <NewReportForm internship={internship} reports={reports} />}
      {reports.length === 0 && <p className="empty">Aucun rapport déposé pour l'instant.</p>}
      <ol className="reports">
        {reports.map((report) => (
          <li key={report.id} className="report">
            <header className="report__head">
              <h3>
                Semaine du {formatShortDay(report.week_start)} au {formatShortDay(report.week_end)}
              </h3>
              <span className={`badge badge--report-${report.status}`}>
                {report.status === "reviewed" ? "Relu" : "À relire"}
              </span>
            </header>
            <dl className="report__body">
              <dt>Réalisations</dt>
              <dd>{report.accomplishments}</dd>
              {report.difficulties && (
                <>
                  <dt>Difficultés</dt>
                  <dd>{report.difficulties}</dd>
                </>
              )}
              {report.next_steps && (
                <>
                  <dt>Prochaines étapes</dt>
                  <dd>{report.next_steps}</dd>
                </>
              )}
              {report.feedback && (
                <>
                  <dt>Retour de l'encadrant</dt>
                  <dd className="report__feedback">{report.feedback}</dd>
                </>
              )}
            </dl>
            {canReview && report.status === "submitted" && (
              <ReviewForm internshipId={internship.id} reportId={report.id} />
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}

/** Semaines commencées du stage, sans rapport : celles qu'on peut encore déposer. */
function openWeeks(internship: Internship, reports: Report[]) {
  const done = new Set(reports.map((r) => r.week));
  const current = isoWeekOf(todayUtc()).key;
  const weeks = weeksBetween(parseDay(internship.start_date), parseDay(internship.end_date));
  const lastIndex = weeks.findIndex((w) => w.key === current);
  const started = lastIndex === -1 ? weeks : weeks.slice(0, lastIndex + 1);
  return started.filter((w) => !done.has(w.key)).reverse();
}

function NewReportForm({ internship, reports }: { internship: Internship; reports: Report[] }) {
  const submit = useSubmitReport(internship.id);
  const weeks = openWeeks(internship, reports);

  function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const field = readForm(formElement);
    submit.mutate(
      {
        week: field("week"),
        accomplishments: field("accomplishments"),
        difficulties: field("difficulties"),
        next_steps: field("next_steps"),
      },
      {
        onSuccess: () => {
          formElement.reset();
        },
      },
    );
  }

  if (weeks.length === 0) {
    return <p className="hint">Tous les rapports des semaines écoulées sont déposés.</p>;
  }

  return (
    <details className="panel" open>
      <summary>Déposer le rapport de la semaine</summary>
      <form className="form" onSubmit={handleSubmit}>
        <label>
          Semaine
          <select name="week" defaultValue={weeks[0]?.key}>
            {weeks.map((week) => (
              <option key={week.key} value={week.key}>
                Semaine du {formatShortDay(week.monday.toISOString())}
              </option>
            ))}
          </select>
        </label>
        <label>
          Ce que j'ai réalisé
          <textarea name="accomplishments" rows={4} required maxLength={5000} />
        </label>
        <label>
          Difficultés rencontrées
          <textarea name="difficulties" rows={2} maxLength={5000} />
        </label>
        <label>
          Prochaines étapes
          <textarea name="next_steps" rows={2} maxLength={5000} />
        </label>
        <ErrorAlert error={submit.error} />
        <button type="submit" className="button" disabled={submit.isPending}>
          Déposer le rapport
        </button>
      </form>
    </details>
  );
}

function ReviewForm({ internshipId, reportId }: { internshipId: string; reportId: string }) {
  const review = useReviewReport(internshipId);
  const [feedback, setFeedback] = useState("");

  function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    review.mutate({ reportId, feedback });
  }

  return (
    <form className="form report__review" onSubmit={handleSubmit}>
      <label>
        Votre retour
        <textarea
          rows={2}
          required
          maxLength={2000}
          value={feedback}
          onChange={(e) => {
            setFeedback(e.target.value);
          }}
        />
      </label>
      <ErrorAlert error={review.error} />
      <button type="submit" className="button" disabled={review.isPending}>
        Valider la relecture
      </button>
    </form>
  );
}
