import createClient, { type Middleware } from "openapi-fetch";

import { SESSION_EXPIRED_EVENT, session } from "../auth/session";
import { toApiError } from "./problem";
import type { paths } from "./schema";

const LOGIN_PATH = "/api/v1/auth/token";

const auth: Middleware = {
  onRequest({ request }) {
    const token = session.get();
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
  onResponse({ request, response }) {
    // Jeton expiré ou révoqué : on oublie la session et l'application revient à
    // la page de connexion. Un échec de connexion, lui, reste affiché tel quel.
    if (response.status === 401 && !new URL(request.url).pathname.endsWith(LOGIN_PATH)) {
      session.clear();
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    }
    return response;
  },
};

// URL absolue (même origine) : en production nginx relaie /api vers le service API.
// `fetch` est résolu à chaque appel (et non capturé à l'import) : les outils qui
// l'instrumentent, comme MSW dans les tests, fonctionnent alors sans configuration.
export const api = createClient<paths>({
  baseUrl: window.location.origin,
  fetch: (request) => globalThis.fetch(request),
});
api.use(auth);

interface FetchResult<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

/** Renvoie les données, ou lève une ApiError lisible (RFC 9457). */
export async function unwrap<T>(request: Promise<FetchResult<T>>): Promise<T> {
  const { data, error, response } = await request;
  if (!response.ok) throw toApiError(response.status, error);
  return data as T;
}
