/**
 * Semaines ISO 8601 (du lundi au dimanche), calculées comme l'API : « 2026-W41 ».
 * Toutes les dates sont manipulées en UTC pour éviter les décalages de fuseau.
 */
const DAY_MS = 86_400_000;

export interface IsoWeek {
  key: string; // « 2026-W41 »
  monday: Date;
}

function mondayOf(date: Date): Date {
  const day = (date.getUTCDay() + 6) % 7; // lundi = 0
  return new Date(date.getTime() - day * DAY_MS);
}

export function isoWeekOf(date: Date): IsoWeek {
  const monday = mondayOf(date);
  const thursday = new Date(monday.getTime() + 3 * DAY_MS);
  const year = thursday.getUTCFullYear(); // l'année ISO est celle du jeudi
  const firstThursday = new Date(Date.UTC(year, 0, 4));
  const week =
    1 + Math.round((monday.getTime() - mondayOf(firstThursday).getTime()) / (7 * DAY_MS));
  return { key: `${year}-W${String(week).padStart(2, "0")}`, monday };
}

/** Toutes les semaines touchées par la période, dans l'ordre. */
export function weeksBetween(start: Date, end: Date): IsoWeek[] {
  const weeks: IsoWeek[] = [];
  for (
    let monday = mondayOf(start);
    monday <= end;
    monday = new Date(monday.getTime() + 7 * DAY_MS)
  ) {
    weeks.push(isoWeekOf(monday));
  }
  return weeks;
}

export function todayUtc(now: Date = new Date()): Date {
  return new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()));
}
