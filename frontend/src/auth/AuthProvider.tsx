import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, unwrap } from "../api/client";
import { keys } from "../api/queries";
import { AuthContext } from "./context";
import { SESSION_EXPIRED_EVENT, session } from "./session";

export function AuthProvider({ children }: { children: ReactNode }) {
  const client = useQueryClient();
  const [token, setToken] = useState(() => session.get());

  const meQuery = useQuery({
    queryKey: keys.me,
    queryFn: () => unwrap(api.GET("/api/v1/auth/me")),
    enabled: token !== null,
    staleTime: Infinity,
    retry: false,
  });

  const logout = useCallback(() => {
    session.clear();
    setToken(null);
    client.clear(); // aucune donnée de l'utilisateur précédent ne doit rester en cache
  }, [client]);

  useEffect(() => {
    window.addEventListener(SESSION_EXPIRED_EVENT, logout);
    return () => {
      window.removeEventListener(SESSION_EXPIRED_EVENT, logout);
    };
  }, [logout]);

  const login = useCallback(
    async (email: string, password: string) => {
      const { access_token } = await unwrap(
        api.POST("/api/v1/auth/token", {
          body: { username: email, password, grant_type: "password", scope: "" },
          bodySerializer: (body) => new URLSearchParams(body as Record<string, string>),
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
        }),
      );
      session.set(access_token);
      client.clear();
      setToken(access_token);
    },
    [client],
  );

  const me = token === null ? null : meQuery.isError ? null : meQuery.data;
  const value = useMemo(() => ({ me, login, logout }), [me, login, logout]);
  return <AuthContext value={value}>{children}</AuthContext>;
}
