import { useState, type SubmitEvent } from "react";

import { useCreateIntern, useInterns } from "../api/queries";
import type { StudyLevel } from "../api/types";
import { ErrorAlert } from "../components/ErrorAlert";
import { Pagination } from "../components/Pagination";
import { useMe } from "../auth/useAuth";
import { STUDY_LEVEL_LABELS, fullName, plural } from "../lib/format";
import { readForm } from "../lib/forms";

export function InternsPage() {
  const me = useMe();
  const [offset, setOffset] = useState(0);
  const { data, error, isPending } = useInterns(offset);

  return (
    <section>
      <header className="page-header">
        <h1>Stagiaires</h1>
        {data && (
          <p className="page-header__count">
            {plural(data.total, "stagiaire inscrit", "stagiaires inscrits")}
          </p>
        )}
      </header>
      {me.role === "hr" && <NewInternForm />}
      <ErrorAlert error={error} />
      {isPending && <p className="loading">Chargement…</p>}
      {data && (
        <>
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Nom</th>
                <th scope="col">E-mail</th>
                <th scope="col">École</th>
                <th scope="col">Niveau</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((intern) => (
                <tr key={intern.id}>
                  <td>{fullName(intern)}</td>
                  <td>{intern.email}</td>
                  <td>{intern.school}</td>
                  <td>{STUDY_LEVEL_LABELS[intern.study_level]}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.items.length === 0 && (
            <p className="empty">Aucun stagiaire inscrit pour l'instant.</p>
          )}
          <Pagination {...data} onChange={setOffset} />
        </>
      )}
    </section>
  );
}

function NewInternForm() {
  const create = useCreateIntern();

  function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const field = readForm(formElement);
    create.mutate(
      {
        first_name: field("first_name"),
        last_name: field("last_name"),
        email: field("email"),
        school: field("school"),
        study_level: field("study_level") as StudyLevel,
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
      <summary>Inscrire un stagiaire</summary>
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
          École
          <input name="school" required maxLength={150} />
        </label>
        <label>
          Niveau d'études
          <select name="study_level" defaultValue="ingenieur">
            {Object.entries(STUDY_LEVEL_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <div className="form__actions">
          <ErrorAlert error={create.error} />
          {create.isSuccess && <p role="status">Stagiaire inscrit.</p>}
          <button type="submit" className="button" disabled={create.isPending}>
            Inscrire le stagiaire
          </button>
        </div>
      </form>
    </details>
  );
}
