import { screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ongoing, planned } from "../../test/fixtures";
import { renderApp } from "../../test/render";
import { received } from "../../test/server";

describe("page d'un stage", () => {
  beforeEach(() => {
    // Seule la date est figée : les minuteries restent réelles pour MSW et user-event.
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-10-14T10:00:00Z")); // mercredi de la semaine 2026-W42
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("présente le stage, ses tâches et ses rapports", async () => {
    renderApp(`/stages/${ongoing.id}`, { as: "supervisor" });
    expect(await screen.findByRole("heading", { name: ongoing.subject })).toBeInTheDocument();
    expect(await screen.findByText("Sara El Amrani avec Karim Benali")).toBeInTheDocument();
    expect(await screen.findByText("Modéliser la base de données")).toBeInTheDocument();
    expect(screen.getByText("Semaine du 28 sept. au 4 oct.")).toBeInTheDocument();
  });

  it("montre la régularité des rapports semaine par semaine", async () => {
    renderApp(`/stages/${ongoing.id}`, { as: "supervisor" });
    expect(await screen.findByText(/1 rapport déposé sur 12 semaines/)).toBeInTheDocument();
    expect(screen.getByText(/1 manquant/)).toBeInTheDocument();
    expect(screen.getByText("Semaine 1 (2026-W40) : rapport à relire")).toBeInTheDocument();
    expect(screen.getByText("Semaine 2 (2026-W41) : rapport manquant")).toBeInTheDocument();
    expect(screen.getByText("Semaine 3 (2026-W42) : semaine en cours")).toBeInTheDocument();
    expect(screen.getByText("Semaine 4 (2026-W43) : à venir")).toBeInTheDocument();
  });

  it("permet à l'encadrant de confier une tâche", async () => {
    const { user } = renderApp(`/stages/${ongoing.id}`, { as: "supervisor" });
    await user.click(await screen.findByText("Confier une tâche"));
    await user.type(screen.getByLabelText("Intitulé"), "Écrire les tests");
    await user.type(screen.getByLabelText("Échéance"), "2026-10-23");
    await user.click(screen.getByRole("button", { name: "Confier la tâche" }));

    expect(await screen.findByText("Écrire les tests")).toBeInTheDocument();
    expect(received.at(-1)).toEqual({
      path: "tasks",
      body: { title: "Écrire les tests", description: "", due_date: "2026-10-23" },
    });
  });

  it("fait avancer une tâche", async () => {
    const { user } = renderApp(`/stages/${ongoing.id}`, { as: "intern" });
    const task = (await screen.findByText("Modéliser la base de données")).closest("li");
    await user.click(within(task as HTMLElement).getByRole("button", { name: "Commencer" }));
    expect(await within(task as HTMLElement).findByText("En cours")).toBeInTheDocument();
    await user.click(within(task as HTMLElement).getByRole("button", { name: "Marquer terminée" }));
    expect(await within(task as HTMLElement).findByText("Terminée")).toBeInTheDocument();
  });

  it("permet à l'encadrant de relire un rapport", async () => {
    const { user } = renderApp(`/stages/${ongoing.id}`, { as: "supervisor" });
    await user.type(await screen.findByLabelText("Votre retour"), "Bon début, continue.");
    await user.click(screen.getByRole("button", { name: "Valider la relecture" }));

    expect(await screen.findByText("Bon début, continue.")).toBeInTheDocument();
    expect(screen.getByText("Relu")).toBeInTheDocument();
  });

  it("permet au stagiaire de déposer le rapport d'une semaine sans rapport", async () => {
    const { user } = renderApp(`/stages/${ongoing.id}`, { as: "intern" });
    const week = await screen.findByLabelText("Semaine");
    // W40 a déjà un rapport : seules W42 (en cours) et W41 sont proposées.
    expect(
      within(week)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["Semaine du 12 oct.", "Semaine du 5 oct."]);
    await user.selectOptions(week, "2026-W41");
    await user.type(screen.getByLabelText("Ce que j'ai réalisé"), "Modèle de données terminé");
    await user.click(screen.getByRole("button", { name: "Déposer le rapport" }));

    expect(await screen.findByText("Modèle de données terminé")).toBeInTheDocument();
    expect(received.at(-1)).toMatchObject({
      path: "reports",
      body: { week: "2026-W41", accomplishments: "Modèle de données terminé" },
    });
    expect(screen.queryByLabelText("Votre retour")).not.toBeInTheDocument();
  });

  it("propose à l'encadrant de démarrer un stage prévu", async () => {
    const { user } = renderApp(`/stages/${planned.id}`, { as: "supervisor" });
    await user.click(await screen.findByRole("button", { name: "Démarrer le stage" }));
    expect(await screen.findByRole("button", { name: "Terminer le stage" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Annuler le stage" })).not.toBeInTheDocument();
  });

  it("réserve l'annulation aux RH", async () => {
    const { user } = renderApp(`/stages/${ongoing.id}`, { as: "hr" });
    await user.click(await screen.findByRole("button", { name: "Annuler le stage" }));
    expect(await screen.findByText("Annulé")).toBeInTheDocument();
    expect(screen.queryByText("Confier une tâche")).not.toBeInTheDocument();
  });

  it("explique quand le stage n'existe pas ou n'est pas visible", async () => {
    renderApp("/stages/inconnu", { as: "intern" });
    expect(await screen.findByRole("alert")).toHaveTextContent("Stage introuvable.");
    expect(screen.getByRole("link", { name: "Mon stage" })).toBeInTheDocument();
  });
});
