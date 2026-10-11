import { useState, type SubmitEvent } from "react";

import { useCreateSupervisor, useSupervisors } from "../api/queries";
import { ErrorAlert } from "../components/ErrorAlert";
import { Pagination } from "../components/Pagination";
import { useMe } from "../auth/useAuth";
import { fullName, plural } from "../lib/format";
import { readForm } from "../lib/forms";

export function SupervisorsPage() {
  const me = useMe();
  const [offset, setOffset] = useState(0);
  const { data, error, isPending } = useSupervisors(offset);

  return (
    <section>
      <header className="page-header">
        <h1>Encadrants</h1>
        {data && (
          <p className="page-header__count">{plural(data.total, "encadrant", "encadrants")}</p>
        )}
      </header>
      {me.role === "hr" && <NewSupervisorForm />}
      <ErrorAlert error={error} />
      {isPending && <p className="loading">Chargement…</p>}
      {data && (
        <>
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Nom</th>
                <th scope="col">E-mail</th>
                <th scope="col">Département</th>
                <th scope="col" className="numeric">
                  Capacité
                </th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((supervisor) => (
                <tr key={supervisor.id}>
                  <td>{fullName(supervisor)}</td>
                  <td>{supervisor.email}</td>
                  <td>{supervisor.department}</td>
                  <td className="numeric">{supervisor.max_interns} stagiaires</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.items.length === 0 && <p className="empty">Aucun encadrant enregistré.</p>}
          <Pagination {...data} onChange={setOffset} />
        </>
      )}
    </section>
  );
}

function NewSupervisorForm() {
  const create = useCreateSupervisor();

  function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const field = readForm(formElement);
    create.mutate(
      {
        first_name: field("first_name"),
        last_name: field("last_name"),
        email: field("email"),
        department: field("department"),
        max_interns: Number(field("max_interns")),
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
      <summary>Enregistrer un encadrant</summary>
      <form className="form form--grid" onSubmit={handleSubmit}>
        <label>
          Prénom
          <input name="first_name" required maxLength={100} />
        </label>
        <label>
          Nom
          <input name="last_name" required maxLength={100} />
        </label>
        <label>
          Adresse e-mail
          <input name="email" type="email" required />
        </label>
        <label>
          Département
          <input name="department" required maxLength={100} />
        </label>
        <label>
          Stagiaires encadrés au maximum
          <input name="max_interns" type="number" min={1} max={10} defaultValue={3} required />
        </label>
        <div className="form__actions">
          <ErrorAlert error={create.error} />
          {create.isSuccess && <p role="status">Encadrant enregistré.</p>}
          <button type="submit" className="button" disabled={create.isPending}>
            Enregistrer l'encadrant
          </button>
        </div>
      </form>
    </details>
  );
}
