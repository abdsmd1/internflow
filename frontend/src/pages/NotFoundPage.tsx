import { Link } from "react-router";

export function NotFoundPage() {
  return (
    <section className="empty">
      <h1>Page introuvable</h1>
      <p>Cette adresse ne correspond à aucune page, ou vous n'avez pas accès à ce contenu.</p>
      <Link to="/stages">Revenir aux stages</Link>
    </section>
  );
}
