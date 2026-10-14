import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type { ChatResponse } from "../api/types";
import { renderApp } from "../test/render";
import { server } from "../test/server";

const THREAD = "77777777-7777-4777-8777-777777777777";
const CHAT = "*/api/v1/agent/chat";
const DECISION = `*/api/v1/agent/threads/${THREAD}/decision`;

function reply(text: string, tools: string[] = []): ChatResponse {
  return { thread_id: THREAD, reply: text, tools_used: tools, pending_action: null };
}

const proposal: ChatResponse = {
  thread_id: THREAD,
  reply: null,
  tools_used: [],
  pending_action: {
    kind: "create_task",
    internship_id: "stage-1",
    internship_subject: "Agent IA de suivi des stagiaires",
    title: "Préparer la démo",
    due_date: "2026-10-30",
    description: "Démo de fin de sprint",
  },
};

describe("assistant", () => {
  it("répond à une question suggérée en citant ce qu'il a consulté", async () => {
    const bodies: unknown[] = [];
    server.use(
      http.post(CHAT, async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json(
          bodies.length === 1
            ? reply("Une tâche est en retard : « Modéliser la base ».", ["taches_en_retard"])
            : reply("Elle est confiée à Sara El Amrani."),
        );
      }),
    );
    const { user } = renderApp("/assistant", { as: "supervisor" });

    await user.click(
      await screen.findByRole("button", { name: "Quelles tâches sont en retard ?" }),
    );
    expect(
      await screen.findByText("Une tâche est en retard : « Modéliser la base »."),
    ).toBeVisible();
    expect(screen.getByText("Consulté : tâches en retard")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Votre question"), "À qui ?{Enter}");
    expect(await screen.findByText("Elle est confiée à Sara El Amrani.")).toBeVisible();
    // La conversation continue : le second message porte l'identifiant reçu.
    expect(bodies).toEqual([
      { message: "Quelles tâches sont en retard ?" },
      { message: "À qui ?", thread_id: THREAD },
    ]);
  });

  it("demande une confirmation avant de créer une tâche", async () => {
    const decisions: unknown[] = [];
    server.use(
      http.post(CHAT, () => HttpResponse.json(proposal)),
      http.post(DECISION, async ({ request }) => {
        decisions.push(await request.json());
        return HttpResponse.json(reply("C'est fait : la tâche est créée.", ["proposer_tache"]));
      }),
    );
    const { user } = renderApp("/assistant", { as: "supervisor" });
    await user.type(await screen.findByLabelText("Votre question"), "Ajoute une tâche démo");
    await user.click(screen.getByRole("button", { name: "Envoyer" }));

    expect(
      await screen.findByRole("heading", { name: /propose de créer une tâche/ }),
    ).toBeVisible();
    expect(screen.getByText("Préparer la démo")).toBeInTheDocument();
    expect(screen.getByText("30 oct. 2026")).toBeInTheDocument();
    expect(screen.getByLabelText("Votre question")).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Créer la tâche" }));
    expect(await screen.findByText("C'est fait : la tâche est créée.")).toBeVisible();
    expect(screen.queryByRole("heading", { name: /propose/ })).not.toBeInTheDocument();
    expect(decisions).toEqual([{ approved: true }]);
  });

  it("transmet un refus", async () => {
    const decisions: unknown[] = [];
    server.use(
      http.post(CHAT, () => HttpResponse.json(proposal)),
      http.post(DECISION, async ({ request }) => {
        decisions.push(await request.json());
        return HttpResponse.json(reply("D'accord, je n'ai rien créé."));
      }),
    );
    const { user } = renderApp("/assistant", { as: "hr" });
    await user.type(await screen.findByLabelText("Votre question"), "Ajoute une tâche{Enter}");
    await user.click(await screen.findByRole("button", { name: "Refuser" }));

    expect(await screen.findByText("D'accord, je n'ai rien créé.")).toBeVisible();
    expect(decisions).toEqual([{ approved: false }]);
  });

  it("explique quand le modèle ne répond pas", async () => {
    server.use(
      http.post(CHAT, () =>
        HttpResponse.json(
          {
            type: "x/model-unavailable",
            title: "Erreur",
            status: 503,
            detail: "Ollama est arrêté.",
          },
          { status: 503 },
        ),
      ),
    );
    const { user } = renderApp("/assistant", { as: "hr" });
    await user.click(await screen.findByRole("button", { name: "Liste les stages en cours." }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Ollama est arrêté.");
  });

  it("indique comment démarrer l'assistant quand il n'est pas lancé", async () => {
    server.use(
      http.post(CHAT, () => new HttpResponse("<html>502 Bad Gateway</html>", { status: 502 })),
    );
    const { user } = renderApp("/assistant", { as: "hr" });
    await user.click(await screen.findByRole("button", { name: "Liste les stages en cours." }));
    expect(await screen.findByRole("alert")).toHaveTextContent("docker compose --profile ai up -d");
  });

  it("repart d'une conversation vierge", async () => {
    server.use(http.post(CHAT, () => HttpResponse.json(reply("Bonjour !"))));
    const { user } = renderApp("/assistant", { as: "intern" });
    await user.type(await screen.findByLabelText("Votre question"), "Bonjour{Enter}");
    await screen.findByText("Bonjour !");

    await user.click(screen.getByRole("button", { name: "Nouvelle conversation" }));
    expect(screen.queryByText("Bonjour !")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Quelles tâches sont en retard ?" })).toBeVisible();
  });

  it("n'envoie pas de message vide", async () => {
    const { user } = renderApp("/assistant", { as: "hr" });
    await user.type(await screen.findByLabelText("Votre question"), "   {Enter}");
    expect(screen.getByRole("button", { name: "Envoyer" })).toBeDisabled();
    expect(screen.queryByText("Vous")).not.toBeInTheDocument();
  });
});
