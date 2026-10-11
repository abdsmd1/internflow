import type { Internship, Report } from "../../api/types";
import { parseDay, plural } from "../../lib/format";
import { todayUtc, weeksBetween } from "../../lib/isoWeek";

type WeekState = "reviewed" | "submitted" | "missing" | "current" | "upcoming" | "none";

const STATE_LABELS: Record<WeekState, string> = {
  reviewed: "rapport relu",
  submitted: "rapport à relire",
  missing: "rapport manquant",
  current: "semaine en cours",
  upcoming: "à venir",
  none: "pas de rapport attendu",
};

const LEGEND: WeekState[] = ["reviewed", "submitted", "missing", "current", "upcoming"];
const DAY_MS = 86_400_000;

/**
 * Une case par semaine ISO du stage : on voit d'un coup d'œil la régularité des
 * rapports hebdomadaires, sans ouvrir chaque rapport.
 */
export function WeekStrip({
  internship,
  reports,
  today = todayUtc(),
}: {
  internship: Internship;
  reports: Report[];
  today?: Date;
}) {
  const byWeek = new Map(reports.map((report) => [report.week, report]));
  const expectsReports = internship.status === "ongoing" || internship.status === "completed";

  const weeks = weeksBetween(parseDay(internship.start_date), parseDay(internship.end_date)).map(
    (week, index) => {
      const sunday = new Date(week.monday.getTime() + 6 * DAY_MS);
      const report = byWeek.get(week.key);
      let state: WeekState;
      if (report) state = report.status === "reviewed" ? "reviewed" : "submitted";
      else if (week.monday > today) state = "upcoming";
      else if (sunday >= today) state = "current";
      else state = expectsReports ? "missing" : "none";
      return { ...week, number: index + 1, state };
    },
  );

  const done = weeks.filter((w) => w.state === "reviewed" || w.state === "submitted").length;
  const missing = weeks.filter((w) => w.state === "missing").length;

  return (
    <section className="weeks" aria-labelledby="weeks-title">
      <div className="weeks__head">
        <h2 id="weeks-title">Rapports hebdomadaires</h2>
        <p>
          {plural(done, "rapport déposé", "rapports déposés")} sur{" "}
          {plural(weeks.length, "semaine", "semaines")}
          {missing > 0 && (
            <strong className="weeks__missing">, {plural(missing, "manquant", "manquants")}</strong>
          )}
        </p>
      </div>
      <ol className="weeks__strip">
        {weeks.map((week) => (
          <li
            key={week.key}
            className={`week week--${week.state}`}
            title={`Semaine ${week.number} (${week.key}) : ${STATE_LABELS[week.state]}`}
          >
            <span className="visually-hidden">
              Semaine {week.number} ({week.key}) : {STATE_LABELS[week.state]}
            </span>
          </li>
        ))}
      </ol>
      <ul className="weeks__legend" aria-hidden="true">
        {LEGEND.map((state) => (
          <li key={state}>
            <span className={`week week--${state}`} />
            {STATE_LABELS[state]}
          </li>
        ))}
      </ul>
    </section>
  );
}
