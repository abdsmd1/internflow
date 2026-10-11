import { NavLink, Outlet } from "react-router";

import { useAuth, useMe } from "../auth/useAuth";
import { ROLE_LABELS } from "../lib/format";

export function Layout() {
  const me = useMe();
  const { logout } = useAuth();
  return (
    <div className="shell">
      <header className="sidebar">
        <p className="brand">InternFlow</p>
        <nav aria-label="Navigation principale">
          <ul>
            <li>
              <NavLink to="/stages">{me.role === "intern" ? "Mon stage" : "Stages"}</NavLink>
            </li>
            {me.role !== "intern" && (
              <li>
                <NavLink to="/stagiaires">Stagiaires</NavLink>
              </li>
            )}
            <li>
              <NavLink to="/encadrants">Encadrants</NavLink>
            </li>
          </ul>
        </nav>
        <div className="sidebar__account">
          <p>{ROLE_LABELS[me.role]}</p>
          <button type="button" className="button button--quiet" onClick={logout}>
            Se déconnecter
          </button>
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
