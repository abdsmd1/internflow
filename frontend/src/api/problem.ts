/** Erreur renvoyée par l'API au format RFC 9457 (« problem details »). */
export interface Problem {
  type: string;
  title: string;
  status: number;
  detail: string;
  errors?: { location: (string | number)[]; message: string }[];
}

export class ApiError extends Error {
  readonly status: number;
  readonly problem: Problem;

  constructor(status: number, problem: Problem) {
    super(problem.detail);
    this.name = "ApiError";
    this.status = status;
    this.problem = problem;
  }
}

function isProblem(value: unknown): value is Problem {
  return typeof value === "object" && value !== null && "detail" in value && "status" in value;
}

export function toApiError(status: number, body: unknown): ApiError {
  if (isProblem(body)) return new ApiError(status, body);
  return new ApiError(status, {
    type: "about:blank",
    title: "Erreur",
    status,
    detail: "Le serveur a renvoyé une réponse inattendue. Réessayez dans un instant.",
  });
}

/** Message lisible pour l'utilisateur, quelle que soit l'erreur. */
export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    const fields = error.problem.errors
      ?.map((e) => `${String(e.location.at(-1) ?? "")} : ${e.message}`)
      .join(" ; ");
    return fields ? `${error.problem.detail} (${fields})` : error.problem.detail;
  }
  if (error instanceof TypeError) {
    return "Impossible de joindre le serveur. Vérifiez que l'API est démarrée.";
  }
  return "Une erreur inattendue est survenue.";
}
