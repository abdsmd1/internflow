import { useState, type SubmitEvent } from "react";
import { Navigate, useLocation } from "react-router";

import { ErrorAlert } from "../components/ErrorAlert";
import { useAuth } from "../auth/useAuth";
import { readForm } from "../lib/forms";

export function LoginPage() {
  const { me, login } = useAuth();
  const location = useLocation();
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  if (me) {
    const from = (location.state as { from?: string } | null)?.from ?? "/stages";
    return <Navigate to={from} replace />;
  }

  async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const field = readForm(event.currentTarget);
    setPending(true);
    setError(null);
    try {
      await login(field("email"), field("password"));
    } catch (err) {
      setError(err);
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="login">
      <section className="login__panel">
        <h1 className="brand brand--large">InternFlow</h1>
        <p className="login__intro">
          Le suivi des stages, des tâches et des rapports hebdomadaires.
        </p>
        <form onSubmit={(e) => void handleSubmit(e)} className="form">
          <label>
            Adresse e-mail
            <input name="email" type="email" autoComplete="username" required />
          </label>
          <label>
            Mot de passe
            <input name="password" type="password" autoComplete="current-password" required />
          </label>
          <ErrorAlert error={error} />
          <button type="submit" className="button" disabled={pending}>
            {pending ? "Connexion…" : "Se connecter"}
          </button>
        </form>
      </section>
    </main>
  );
}
