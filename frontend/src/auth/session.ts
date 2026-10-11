/**
 * Stockage du jeton d'accès.
 *
 * sessionStorage plutôt que localStorage : le jeton disparaît à la fermeture de
 * l'onglet, et n'est pas partagé entre onglets. Ce choix (et ses limites face au
 * XSS) est expliqué dans l'ADR 0010.
 */
const TOKEN_KEY = "internflow.token";

export const session = {
  get(): string | null {
    return sessionStorage.getItem(TOKEN_KEY);
  },
  set(token: string): void {
    sessionStorage.setItem(TOKEN_KEY, token);
  },
  clear(): void {
    sessionStorage.removeItem(TOKEN_KEY);
  },
};

/** Prévient l'application qu'une session a expiré (réponse 401 de l'API). */
export const SESSION_EXPIRED_EVENT = "internflow:session-expired";
