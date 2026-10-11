import { useContext } from "react";

import { AuthContext, type AuthState } from "./context";

export function useAuth(): AuthState {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error("useAuth doit être utilisé dans <AuthProvider>.");
  return auth;
}

/** L'utilisateur connecté ; à n'utiliser que sous une route protégée. */
export function useMe() {
  const { me } = useAuth();
  if (!me) throw new Error("useMe exige un utilisateur connecté.");
  return me;
}
