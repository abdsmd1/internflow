import { Navigate, Outlet, useLocation } from "react-router";

import { useAuth } from "../auth/useAuth";

export function RequireAuth() {
  const { me } = useAuth();
  const location = useLocation();
  if (me === undefined) return <p className="loading">Chargement…</p>;
  if (me === null) return <Navigate to="/connexion" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}
