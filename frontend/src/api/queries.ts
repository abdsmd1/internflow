/**
 * Accès aux données : une fonction par besoin de l'interface, au-dessus du client typé.
 * TanStack Query gère le cache, les états de chargement et le rafraîchissement.
 */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "./client";
import type {
  InternCreate,
  InternshipCreate,
  InternshipStatus,
  ReportCreate,
  SupervisorCreate,
  TaskCreate,
} from "./types";

export const PAGE_SIZE = 20;

export const keys = {
  me: ["me"] as const,
  interns: (offset: number) => ["interns", offset] as const,
  intern: (id: string) => ["intern", id] as const,
  supervisors: (offset: number) => ["supervisors", offset] as const,
  supervisor: (id: string) => ["supervisor", id] as const,
  internships: (status: InternshipStatus | null, offset: number) =>
    ["internships", status, offset] as const,
  internship: (id: string) => ["internship", id] as const,
  tasks: (internshipId: string) => ["tasks", internshipId] as const,
  reports: (internshipId: string) => ["reports", internshipId] as const,
};

// ---------------------------------------------------------------- lectures

export function useInterns(offset: number) {
  return useQuery({
    queryKey: keys.interns(offset),
    queryFn: () =>
      unwrap(api.GET("/api/v1/interns", { params: { query: { offset, limit: PAGE_SIZE } } })),
    placeholderData: keepPreviousData,
  });
}

export function useIntern(id: string) {
  return useQuery({
    queryKey: keys.intern(id),
    queryFn: () =>
      unwrap(api.GET("/api/v1/interns/{intern_id}", { params: { path: { intern_id: id } } })),
    staleTime: 5 * 60_000, // un nom change rarement : inutile de le redemander
  });
}

export function useSupervisors(offset: number, limit = PAGE_SIZE) {
  return useQuery({
    queryKey: [...keys.supervisors(offset), limit],
    queryFn: () => unwrap(api.GET("/api/v1/supervisors", { params: { query: { offset, limit } } })),
    placeholderData: keepPreviousData,
  });
}

export function useSupervisor(id: string) {
  return useQuery({
    queryKey: keys.supervisor(id),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/supervisors/{supervisor_id}", {
          params: { path: { supervisor_id: id } },
        }),
      ),
    staleTime: 5 * 60_000,
  });
}

export function useInternships(status: InternshipStatus | null, offset: number) {
  return useQuery({
    queryKey: keys.internships(status, offset),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/internships", {
          params: { query: { offset, limit: PAGE_SIZE, ...(status ? { status } : {}) } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useInternship(id: string) {
  return useQuery({
    queryKey: keys.internship(id),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/internships/{internship_id}", {
          params: { path: { internship_id: id } },
        }),
      ),
  });
}

export function useTasks(internshipId: string) {
  return useQuery({
    queryKey: keys.tasks(internshipId),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/internships/{internship_id}/tasks", {
          params: { path: { internship_id: internshipId } },
        }),
      ),
  });
}

export function useReports(internshipId: string) {
  return useQuery({
    queryKey: keys.reports(internshipId),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/internships/{internship_id}/reports", {
          params: { path: { internship_id: internshipId } },
        }),
      ),
  });
}

// ---------------------------------------------------------------- écritures

export function useCreateIntern() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: InternCreate) => unwrap(api.POST("/api/v1/interns", { body })),
    onSuccess: () => client.invalidateQueries({ queryKey: ["interns"] }),
  });
}

export function useCreateSupervisor() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: SupervisorCreate) => unwrap(api.POST("/api/v1/supervisors", { body })),
    onSuccess: () => client.invalidateQueries({ queryKey: ["supervisors"] }),
  });
}

export function usePlanInternship() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: InternshipCreate) => unwrap(api.POST("/api/v1/internships", { body })),
    onSuccess: () => client.invalidateQueries({ queryKey: ["internships"] }),
  });
}

export type InternshipAction = "start" | "complete" | "cancel";

export function useInternshipAction(internshipId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (action: InternshipAction) => {
      const params = { params: { path: { internship_id: internshipId } } };
      switch (action) {
        case "start":
          return unwrap(api.POST("/api/v1/internships/{internship_id}/start", params));
        case "complete":
          return unwrap(api.POST("/api/v1/internships/{internship_id}/complete", params));
        case "cancel":
          return unwrap(api.POST("/api/v1/internships/{internship_id}/cancel", params));
      }
    },
    onSuccess: (internship) => {
      client.setQueryData(keys.internship(internshipId), internship);
      return client.invalidateQueries({ queryKey: ["internships"] });
    },
  });
}

export function useCreateTask(internshipId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: TaskCreate) =>
      unwrap(
        api.POST("/api/v1/internships/{internship_id}/tasks", {
          params: { path: { internship_id: internshipId } },
          body,
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.tasks(internshipId) }),
  });
}

export function useTaskAction(internshipId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, action }: { taskId: string; action: "start" | "complete" }) => {
      const params = { params: { path: { task_id: taskId } } };
      return action === "start"
        ? unwrap(api.POST("/api/v1/tasks/{task_id}/start", params))
        : unwrap(api.POST("/api/v1/tasks/{task_id}/complete", params));
    },
    onSuccess: () => client.invalidateQueries({ queryKey: keys.tasks(internshipId) }),
  });
}

export function useSubmitReport(internshipId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: ReportCreate) =>
      unwrap(
        api.POST("/api/v1/internships/{internship_id}/reports", {
          params: { path: { internship_id: internshipId } },
          body,
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.reports(internshipId) }),
  });
}

export function useReviewReport(internshipId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ reportId, feedback }: { reportId: string; feedback: string }) =>
      unwrap(
        api.POST("/api/v1/reports/{report_id}/review", {
          params: { path: { report_id: reportId } },
          body: { feedback },
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.reports(internshipId) }),
  });
}
