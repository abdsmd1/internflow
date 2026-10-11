import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderApp } from "../test/render";
import { received } from "../test/server";

describe("liste des stages", () => {
  it("affiche les noms du stagiaire et de l'encadrant", async () => {
    renderApp("/stages", { as: "hr" });
    const row = (
      await screen.findByRole("link", { name: "Agent IA de suivi des stagiaires" })
    ).closest("tr");
    expect(row).not.toBeNull();
    expect(await within(row as HTMLElement).findByText("Sara El Amrani")).toBeInTheDocument();
    expect(await within(row as HTMLElement).findByText("Karim Benali")).toBeInTheDocument();
    expect(within(row as HTMLElement).getByText("En cours")).toBeInTheDocument();
    expect(screen.getByText("2 stages")).toBeInTheDocument();
  });

  it("filtre par statut", async () => {
    const { user } = renderApp("/stages", { as: "hr" });
    await screen.findByText("Tableau de bord RH");
    await user.click(screen.getByRole("button", { name: "En cours" }));

    expect(await screen.findByText("1 stage")).toBeInTheDocument();
    expect(screen.queryByText("Tableau de bord RH")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "En cours" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("permet aux RH de planifier un stage", async () => {
    const { user } = renderApp("/stages", { as: "hr" });
    await user.click(await screen.findByText("Planifier un stage"));
    await user.type(screen.getByLabelText("Sujet"), "Migration vers Kubernetes");
    await user.selectOptions(
      await screen.findByLabelText("Stagiaire"),
      await screen.findByRole("option", { name: "Sara El Amrani" }),
    );
    await user.selectOptions(
      screen.getByLabelText("Encadrant"),
      await screen.findByRole("option", { name: "Karim Benali (Data & IA)" }),
    );
    await user.type(screen.getByLabelText("Début"), "2026-11-02");
    await user.type(screen.getByLabelText("Fin"), "2027-01-29");
    await user.click(screen.getByRole("button", { name: "Planifier le stage" }));

    expect(await screen.findByText("Stage planifié.")).toBeInTheDocument();
    expect(received.at(-1)).toEqual({
      path: "internships",
      body: {
        subject: "Migration vers Kubernetes",
        intern_id: "11111111-1111-4111-8111-111111111111",
        supervisor_id: "22222222-2222-4222-8222-222222222222",
        start_date: "2026-11-02",
        end_date: "2027-01-29",
      },
    });
  });

  it("ne propose la planification qu'aux RH", async () => {
    renderApp("/stages", { as: "supervisor" });
    await screen.findByText("Tableau de bord RH");
    expect(screen.queryByText("Planifier un stage")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Stagiaires" })).toBeInTheDocument();
  });

  it("présente le stage du stagiaire sans les pages RH", async () => {
    renderApp("/stages", { as: "intern" });
    expect(await screen.findByRole("heading", { name: "Mon stage" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Stagiaires" })).not.toBeInTheDocument();
  });
});
