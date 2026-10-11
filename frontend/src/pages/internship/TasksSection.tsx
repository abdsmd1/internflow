import type { SubmitEvent } from "react";

import { useCreateTask, useTaskAction, useTasks } from "../../api/queries";
import type { Internship } from "../../api/types";
import { ErrorAlert } from "../../components/ErrorAlert";
import { TaskStatusBadge } from "../../components/StatusBadge";
import { formatDay } from "../../lib/format";
import { readForm } from "../../lib/forms";

export function TasksSection({
  internship,
  canAssign,
}: {
  internship: Internship;
  canAssign: boolean;
}) {
  const tasks = useTasks(internship.id);
  const action = useTaskAction(internship.id);
  const active = internship.status === "planned" || internship.status === "ongoing";

  return (
    <section className="section" aria-labelledby="tasks-title">
      <h2 id="tasks-title">Tâches</h2>
      {canAssign && active && <NewTaskForm internship={internship} />}
      <ErrorAlert error={tasks.error ?? action.error} />
      {tasks.data?.length === 0 && (
        <p className="empty">
          {canAssign
            ? "Aucune tâche confiée. Ajoutez la première ci-dessus."
            : "Aucune tâche pour l'instant."}
        </p>
      )}
      <ul className="tasks">
        {tasks.data?.map((task) => (
          <li key={task.id} className="task">
            <div className="task__main">
              <p className="task__title">{task.title}</p>
              {task.description && <p className="task__description">{task.description}</p>}
              <p className="task__meta">Échéance : {formatDay(task.due_date)}</p>
            </div>
            <TaskStatusBadge status={task.status} overdue={task.is_overdue} />
            {active && task.status !== "done" && (
              <div className="task__actions">
                {task.status === "todo" && (
                  <button
                    type="button"
                    className="button button--quiet"
                    disabled={action.isPending}
                    onClick={() => {
                      action.mutate({ taskId: task.id, action: "start" });
                    }}
                  >
                    Commencer
                  </button>
                )}
                <button
                  type="button"
                  className="button button--quiet"
                  disabled={action.isPending}
                  onClick={() => {
                    action.mutate({ taskId: task.id, action: "complete" });
                  }}
                >
                  Marquer terminée
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function NewTaskForm({ internship }: { internship: Internship }) {
  const create = useCreateTask(internship.id);

  function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const field = readForm(formElement);
    create.mutate(
      {
        title: field("title"),
        description: field("description"),
        due_date: field("due_date"),
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
      <summary>Confier une tâche</summary>
      <form className="form form--grid" onSubmit={handleSubmit}>
        <label className="form__wide">
          Intitulé
          <input name="title" required maxLength={150} />
        </label>
        <label className="form__wide">
          Description
          <textarea name="description" rows={3} maxLength={2000} />
        </label>
        <label>
          Échéance
          <input
            name="due_date"
            type="date"
            required
            min={internship.start_date}
            max={internship.end_date}
          />
        </label>
        <div className="form__actions">
          <ErrorAlert error={create.error} />
          <button type="submit" className="button" disabled={create.isPending}>
            Confier la tâche
          </button>
        </div>
      </form>
    </details>
  );
}
