import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderApp } from "../test/render";
import { received } from "../test/server";

describe("stagiaires", () => {
  it("liste les stagiaires", async () => {
    renderApp("/stagiaires", { as: "supervisor" });
    expect(await screen.findByText("Sara El Amrani")).toBeInTheDocument();
    expect(screen.getByText("Cycle ingénieur")).toBeInTheDocument();
    expect(screen.queryByText("Inscrire un stagiaire")).not.toBeInTheDocument();
  });

  it("permet aux RH d'inscrire un stagiaire", async () => {
    const { user } = renderApp("/stagiaires", { as: "hr" });
    await user.click(await screen.findByText("Inscrire un stagiaire"));
    await user.type(screen.getByLabelText("Prénom"), "Yassine");
    await user.type(screen.getByLabelText("Nom"), "Haddad");
    await user.type(screen.getByLabelText("Adresse e-mail"), "yassine@exemple.ma");
    await user.type(screen.getByLabelText("École"), "ENSAO");
    await user.selectOptions(screen.getByLabelText("Niveau d'études"), "master_2");
    await user.click(screen.getByRole("button", { name: "Inscrire le stagiaire" }));

    expect(await screen.findByText("Stagiaire inscrit.")).toBeInTheDocument();
    expect(await screen.findByText("Yassine Haddad")).toBeInTheDocument();
    expect(received.at(-1)).toMatchObject({ path: "interns", body: { study_level: "master_2" } });
  });

  it("affiche le refus de l'API sans perdre la saisie", async () => {
    const { user } = renderApp("/stagiaires", { as: "hr" });
    await user.click(await screen.findByText("Inscrire un stagiaire"));
    await user.type(screen.getByLabelText("Prénom"), "Sara");
    await user.type(screen.getByLabelText("Nom"), "El Amrani");
    await user.type(screen.getByLabelText("Adresse e-mail"), "sara@exemple.ma");
    await user.type(screen.getByLabelText("École"), "ENSAO");
    await user.click(screen.getByRole("button", { name: "Inscrire le stagiaire" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("existe déjà");
    expect(screen.getByLabelText("Adresse e-mail")).toHaveValue("sara@exemple.ma");
  });
});

describe("encadrants", () => {
  it("permet aux RH d'enregistrer un encadrant", async () => {
    const { user } = renderApp("/encadrants", { as: "hr" });
    expect(await screen.findByText("3 stagiaires")).toBeInTheDocument();
    await user.click(screen.getByText("Enregistrer un encadrant"));
    await user.type(screen.getByLabelText("Prénom"), "Nadia");
    await user.type(screen.getByLabelText("Nom"), "Tazi");
    await user.type(screen.getByLabelText("Adresse e-mail"), "nadia@exemple.ma");
    await user.type(screen.getByLabelText("Département"), "Cloud");
    await user.click(screen.getByRole("button", { name: "Enregistrer l'encadrant" }));

    expect(await screen.findByText("Nadia Tazi")).toBeInTheDocument();
    expect(received.at(-1)).toMatchObject({ body: { department: "Cloud", max_interns: 3 } });
  });

  it("reste consultable par un stagiaire, sans formulaire", async () => {
    renderApp("/encadrants", { as: "intern" });
    expect(await screen.findByText("Karim Benali")).toBeInTheDocument();
    expect(screen.queryByText("Enregistrer un encadrant")).not.toBeInTheDocument();
  });

  it("indique une page inconnue", async () => {
    renderApp("/nimporte-quoi", { as: "intern" });
    expect(await screen.findByRole("heading", { name: "Page introuvable" })).toBeInTheDocument();
  });
});
