import type { InternshipStatus, TaskStatus } from "../api/types";
import { INTERNSHIP_STATUS_LABELS, TASK_STATUS_LABELS } from "../lib/format";

export function InternshipStatusBadge({ status }: { status: InternshipStatus }) {
  return <span className={`badge badge--${status}`}>{INTERNSHIP_STATUS_LABELS[status]}</span>;
}

export function TaskStatusBadge({ status, overdue }: { status: TaskStatus; overdue: boolean }) {
  if (overdue) return <span className="badge badge--overdue">En retard</span>;
  return <span className={`badge badge--task-${status}`}>{TASK_STATUS_LABELS[status]}</span>;
}
