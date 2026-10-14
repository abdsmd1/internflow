import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";

import { resetDatabase, server } from "./server";

// jsdom n'implémente pas le défilement : on le neutralise.
Element.prototype.scrollIntoView = () => undefined;

beforeAll(() => {
  // Toute requête non prévue par un test est une erreur : pas d'appel réseau caché.
  server.listen({ onUnhandledRequest: "error" });
});
afterEach(() => {
  cleanup();
  server.resetHandlers();
  resetDatabase();
  sessionStorage.clear();
});
afterAll(() => {
  server.close();
});
