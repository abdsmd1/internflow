/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// En développement, Vite relaie /api vers l'API locale : pas de CORS à configurer,
// et le même chemin relatif fonctionne derrière nginx en production.
const API_TARGET = process.env.INTERNFLOW_API_URL ?? "http://localhost:8000";
const AGENT_TARGET = process.env.INTERNFLOW_AGENT_URL ?? "http://localhost:8100";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // L'ordre compte : la règle la plus précise (l'assistant) doit venir en premier.
    proxy: { "/api/v1/agent": AGENT_TARGET, "/api": API_TARGET, "/health": API_TARGET },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    restoreMocks: true,
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/test/**",
        "src/main.tsx",
        "src/**/*.test.{ts,tsx}",
        "src/api/schema.d.ts",
        "src/api/agent-schema.d.ts",
      ],
      thresholds: { lines: 80, functions: 80, branches: 75, statements: 80 },
    },
  },
});
