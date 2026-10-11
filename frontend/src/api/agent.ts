import { useMutation } from "@tanstack/react-query";

import { agentApi, unwrap } from "./client";

export function useSendMessage() {
  return useMutation({
    mutationFn: ({ message, threadId }: { message: string; threadId: string | null }) =>
      unwrap(
        agentApi.POST("/api/v1/agent/chat", {
          body: { message, ...(threadId ? { thread_id: threadId } : {}) },
        }),
      ),
  });
}

export function useDecide() {
  return useMutation({
    mutationFn: ({ threadId, approved }: { threadId: string; approved: boolean }) =>
      unwrap(
        agentApi.POST("/api/v1/agent/threads/{thread_id}/decision", {
          params: { path: { thread_id: threadId } },
          body: { approved },
        }),
      ),
  });
}
