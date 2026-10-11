import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";

import { App } from "../App";
import type { Role } from "../api/types";
import { AuthProvider } from "../auth/AuthProvider";
import { session } from "../auth/session";
import { tokenFor } from "./server";

/** Monte toute l'application sur une URL, éventuellement déjà connecté. */
export function renderApp(path: string, { as }: { as?: Role } = {}) {
  if (as) session.set(tokenFor(as));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const user = userEvent.setup();
  const view = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { user, ...view };
}
