import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { PASSWORD } from "../test/fixtures";
import { renderApp } from "../test/render";
import { server } from "../test/server";
import { session } from "./session";

describe("connexion", () => {
  it("redirige vers la connexion quand personne n'est connecté", async () => {
    renderApp("/stages");
    expect(await screen.findByRole("button", { name: "Se connecter" })).toBeInTheDocument();
  });

  it("connecte l'utilisateur puis affiche les stages", async () => {
    const { user } = renderApp("/stages");
    await user.type(await screen.findByLabelText("Adresse e-mail"), "rh@exemple.ma");
    await user.type(screen.getByLabelText("Mot de passe"), PASSWORD);
    await user.click(screen.getByRole("button", { name: "Se connecter" }));

    expect(await screen.findByRole("heading", { name: "Stages" })).toBeInTheDocument();
    expect(screen.getByText("Ressources humaines")).toBeInTheDocument();
    expect(session.get()).toBe("jeton-hr");
  });

  it("affiche le message de l'API quand le mot de passe est faux", async () => {
    const { user } = renderApp("/connexion");
    await user.type(await screen.findByLabelText("Adresse e-mail"), "rh@exemple.ma");
    await user.type(screen.getByLabelText("Mot de passe"), "mauvais-mot-de-passe");
    await user.click(screen.getByRole("button", { name: "Se connecter" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("E-mail ou mot de passe incorrect.");
    expect(session.get()).toBeNull();
  });

  it("signale un serveur injoignable", async () => {
    server.use(http.post("*/api/v1/auth/token", () => HttpResponse.error()));
    const { user } = renderApp("/connexion");
    await user.type(await screen.findByLabelText("Adresse e-mail"), "rh@exemple.ma");
    await user.type(screen.getByLabelText("Mot de passe"), PASSWORD);
    await user.click(screen.getByRole("button", { name: "Se connecter" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Impossible de joindre le serveur");
  });

  it("revient à la connexion quand le jeton a expiré", async () => {
    session.set("jeton-expire");
    renderApp("/stages");
    expect(await screen.findByRole("button", { name: "Se connecter" })).toBeInTheDocument();
    expect(session.get()).toBeNull();
  });

  it("déconnecte l'utilisateur et oublie son jeton", async () => {
    const { user } = renderApp("/stages", { as: "hr" });
    await user.click(await screen.findByRole("button", { name: "Se déconnecter" }));
    expect(await screen.findByRole("button", { name: "Se connecter" })).toBeInTheDocument();
    await waitFor(() => {
      expect(session.get()).toBeNull();
    });
  });

  it("n'affiche pas la page de connexion à un utilisateur déjà connecté", async () => {
    renderApp("/connexion", { as: "intern" });
    expect(await screen.findByRole("heading", { name: "Mon stage" })).toBeInTheDocument();
  });
});
