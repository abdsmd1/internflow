import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type SubmitEvent } from "react";

import { useDecide, useSendMessage } from "../api/agent";
import { ApiError, describeError } from "../api/problem";
import type { ChatResponse, PendingTask } from "../api/types";
import { formatDay } from "../lib/format";

interface Entry {
  author: "user" | "assistant";
  text: string;
  tools?: string[];
}

const SUGGESTIONS = [
  "Quelles tâches sont en retard ?",
  "Quels rapports dois-je relire ?",
  "Liste les stages en cours.",
  "Qui a eu des difficultés avec Docker ?",
];

/** Noms des outils de l'agent, tels qu'un utilisateur les comprend. */
const TOOL_LABELS: Record<string, string> = {
  lister_stages: "liste des stages",
  consulter_stage: "détail d'un stage",
  taches_en_retard: "tâches en retard",
  rapports_a_relire: "rapports à relire",
  lire_rapports: "contenu des rapports",
  rechercher_dans_rapports: "recherche dans les rapports",
  proposer_tache: "création de tâche",
};

function assistantError(error: unknown): string {
  // nginx répond 502 sans corps RFC 9457 quand le service n'est pas lancé.
  if (error instanceof ApiError && error.status === 502 && error.problem.type === "about:blank") {
    return "L'assistant n'est pas démarré. Lancez-le avec : docker compose --profile ai up -d";
  }
  return describeError(error);
}

export function AssistantPage() {
  const queryClient = useQueryClient();
  const send = useSendMessage();
  const decide = useDecide();
  const [entries, setEntries] = useState<Entry[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingTask | null>(null);
  const [draft, setDraft] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const busy = send.isPending || decide.isPending;

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [entries, pending, busy]);

  function receive(response: ChatResponse) {
    setThreadId(response.thread_id);
    setPending(response.pending_action);
    if (response.reply) {
      const reply = response.reply;
      setEntries((current) => [
        ...current,
        { author: "assistant", text: reply, tools: response.tools_used },
      ]);
    }
  }

  function ask(message: string) {
    const text = message.trim();
    if (!text || busy) return;
    setEntries((current) => [...current, { author: "user", text }]);
    setDraft("");
    send.mutate({ message: text, threadId }, { onSuccess: receive });
  }

  function answer(approved: boolean) {
    if (!threadId) return;
    decide.mutate(
      { threadId, approved },
      {
        onSuccess: (response) => {
          receive(response);
          // Une tâche a peut-être été créée : les pages de stage doivent se rafraîchir.
          if (approved) void queryClient.invalidateQueries({ queryKey: ["tasks"] });
        },
      },
    );
  }

  function restart() {
    setEntries([]);
    setThreadId(null);
    setPending(null);
    send.reset();
    decide.reset();
  }

  function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    ask(draft);
  }

  const error = send.error ?? decide.error;

  return (
    <section className="assistant">
      <header className="page-header">
        <h1>Assistant</h1>
        {entries.length > 0 && (
          <button type="button" className="button button--quiet" onClick={restart}>
            Nouvelle conversation
          </button>
        )}
      </header>

      <div className="chat" aria-live="polite">
        {entries.length === 0 && (
          <div className="chat__intro">
            <p>
              Posez une question sur les stages, les tâches ou les rapports. L'assistant ne voit que
              ce que vous avez le droit de voir, et ne crée rien sans votre accord.
            </p>
            <div className="filters">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  className="chip"
                  onClick={() => {
                    ask(suggestion);
                  }}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {entries.map((entry, index) => (
          <article key={index} className={`message message--${entry.author}`}>
            <p className="message__author">{entry.author === "user" ? "Vous" : "Assistant"}</p>
            <p className="message__text">{entry.text}</p>
            {entry.tools && entry.tools.length > 0 && (
              <p className="message__sources">
                Consulté : {entry.tools.map((tool) => TOOL_LABELS[tool] ?? tool).join(", ")}
              </p>
            )}
          </article>
        ))}

        {pending && (
          <article className="proposal" aria-labelledby="proposal-title">
            <h2 id="proposal-title">L'assistant propose de créer une tâche</h2>
            <dl>
              <dt>Stage</dt>
              <dd>{pending.internship_subject}</dd>
              <dt>Tâche</dt>
              <dd>{pending.title}</dd>
              <dt>Échéance</dt>
              <dd>{formatDay(pending.due_date)}</dd>
              {pending.description && (
                <>
                  <dt>Description</dt>
                  <dd>{pending.description}</dd>
                </>
              )}
            </dl>
            <div className="proposal__actions">
              <button
                type="button"
                className="button"
                disabled={busy}
                onClick={() => {
                  answer(true);
                }}
              >
                Créer la tâche
              </button>
              <button
                type="button"
                className="button button--quiet"
                disabled={busy}
                onClick={() => {
                  answer(false);
                }}
              >
                Refuser
              </button>
            </div>
          </article>
        )}

        {busy && (
          <p className="loading">
            L'assistant réfléchit… (parfois plusieurs minutes avec un modèle local sur processeur)
          </p>
        )}
        {error && (
          <p role="alert" className="alert">
            {assistantError(error)}
          </p>
        )}
        <div ref={endRef} />
      </div>

      <form className="chat__form" onSubmit={handleSubmit}>
        {pending && (
          <p className="hint chat__hint">
            Répondez à la proposition avant de poser une autre question.
          </p>
        )}
        <label className="visually-hidden" htmlFor="question">
          Votre question
        </label>
        <textarea
          id="question"
          rows={2}
          maxLength={2000}
          placeholder="Votre question…"
          value={draft}
          disabled={pending !== null}
          onChange={(e) => {
            setDraft(e.target.value);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              ask(draft);
            }
          }}
        />
        <button
          type="submit"
          className="button"
          disabled={busy || pending !== null || !draft.trim()}
        >
          Envoyer
        </button>
      </form>
    </section>
  );
}
