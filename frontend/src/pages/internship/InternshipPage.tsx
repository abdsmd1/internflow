import { Link, useParams } from "react-router";

import {
  type InternshipAction,
  useInternship,
  useInternshipAction,
  useReports,
} from "../../api/queries";
import { ErrorAlert } from "../../components/ErrorAlert";
import { InternName, SupervisorName } from "../../components/PersonName";
import { InternshipStatusBadge } from "../../components/StatusBadge";
import { useMe } from "../../auth/useAuth";
import { formatPeriod } from "../../lib/format";
import { ReportsSection } from "./ReportsSection";
import { TasksSection } from "./TasksSection";
import { WeekStrip } from "./WeekStrip";

const ACTION_LABELS: Record<InternshipAction, string> = {
  start: "Démarrer le stage",
  complete: "Terminer le stage",
  cancel: "Annuler le stage",
};

export function InternshipPage() {
  const { internshipId = "" } = useParams();
  const me = useMe();
  const internship = useInternship(internshipId);
  const reports = useReports(internshipId);
  const action = useInternshipAction(internshipId);

  if (internship.error) {
    return (
      <section>
        <Link to="/stages" className="back">
          Tous les stages
        </Link>
        <ErrorAlert error={internship.error} />
      </section>
    );
  }
  if (!internship.data) return <p className="loading">Chargement…</p>;

  const data = internship.data;
  // Ces règles ne font que masquer des boutons : l'API reste seule juge (403/409).
  const supervises = me.role === "hr" || me.role === "supervisor";
  const actions: InternshipAction[] = [];
  if (supervises && data.status === "planned") actions.push("start");
  if (supervises && data.status === "ongoing") actions.push("complete");
  if (me.role === "hr" && (data.status === "planned" || data.status === "ongoing")) {
    actions.push("cancel");
  }

  return (
    <article className="internship">
      <Link to="/stages" className="back">
        {me.role === "intern" ? "Mon stage" : "Tous les stages"}
      </Link>
      <header className="internship__head">
        <div>
          <h1>{data.subject}</h1>
          <p className="internship__people">
            <InternName id={data.intern_id} /> avec <SupervisorName id={data.supervisor_id} />
          </p>
          <p className="internship__period">
            {formatPeriod(data.start_date, data.end_date)} ({data.duration_days} jours)
          </p>
        </div>
        <InternshipStatusBadge status={data.status} />
      </header>

      {actions.length > 0 && (
        <div className="internship__actions">
          {actions.map((name) => (
            <button
              key={name}
              type="button"
              className={name === "cancel" ? "button button--danger" : "button"}
              disabled={action.isPending}
              onClick={() => {
                action.mutate(name);
              }}
            >
              {ACTION_LABELS[name]}
            </button>
          ))}
        </div>
      )}
      <ErrorAlert error={action.error ?? reports.error} />

      {reports.data && <WeekStrip internship={data} reports={reports.data} />}
      <div className="internship__columns">
        <TasksSection internship={data} canAssign={supervises} />
        {reports.data && (
          <ReportsSection
            internship={data}
            reports={reports.data}
            canSubmit={me.role === "intern" && data.status === "ongoing"}
            canReview={supervises}
          />
        )}
      </div>
    </article>
  );
}
