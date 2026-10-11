import { createContext } from "react";

import type { Me } from "../api/types";

export interface AuthState {
  /** Utilisateur connecté, `null` si personne, `undefined` pendant la vérification. */
  me: Me | null | undefined;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthState | null>(null);
