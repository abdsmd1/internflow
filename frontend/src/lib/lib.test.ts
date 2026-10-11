import { describe, expect, it } from "vitest";

import { ApiError, describeError, toApiError } from "../api/problem";
import { formatPeriod, plural } from "./format";
import { isoWeekOf, weeksBetween } from "./isoWeek";

const day = (value: string) => new Date(`${value}T00:00:00Z`);

describe("semaines ISO", () => {
  it.each([
    ["2026-10-05", "2026-W41"],
    ["2026-10-11", "2026-W41"],
    ["2027-01-01", "2026-W53"], // le 1er janvier 2027 appartient encore à 2026
    ["2025-12-29", "2026-W01"],
    ["2027-01-04", "2027-W01"],
  ])("%s est dans la semaine %s", (date, key) => {
    expect(isoWeekOf(day(date)).key).toBe(key);
  });

  it("liste toutes les semaines touchées par une période", () => {
    expect(weeksBetween(day("2026-10-01"), day("2026-10-13")).map((w) => w.key)).toEqual([
      "2026-W40",
      "2026-W41",
      "2026-W42",
    ]);
  });
});

describe("mise en forme", () => {
  it("accorde au pluriel", () => {
    expect(plural(1, "stage", "stages")).toBe("1 stage");
    expect(plural(0, "stage", "stages")).toBe("0 stage");
    expect(plural(4, "stage", "stages")).toBe("4 stages");
  });

  it("formate une période sans décalage de fuseau", () => {
    expect(formatPeriod("2026-09-28", "2027-02-11")).toBe("28 sept. 2026 – 11 févr. 2027");
  });
});

describe("erreurs de l'API", () => {
  it("détaille les champs invalides", () => {
    const error = new ApiError(422, {
      type: "validation-error",
      title: "Unprocessable Entity",
      status: 422,
      detail: "La requête contient des données invalides.",
      errors: [{ location: ["body", "email"], message: "adresse invalide" }],
    });
    expect(describeError(error)).toBe(
      "La requête contient des données invalides. (email : adresse invalide)",
    );
  });

  it("reste lisible quand la réponse n'est pas un problème RFC 9457", () => {
    expect(describeError(toApiError(502, "<html>Bad Gateway</html>"))).toMatch(
      /réponse inattendue/,
    );
    expect(describeError(new Error("inconnue"))).toBe("Une erreur inattendue est survenue.");
  });
});
