import type { components } from "./schema";

type Schemas = components["schemas"];

export type Me = Schemas["MeRead"];
export type Role = Schemas["Role"];
export type Intern = Schemas["InternRead"];
export type InternCreate = Schemas["InternCreate"];
export type Supervisor = Schemas["SupervisorRead"];
export type SupervisorCreate = Schemas["SupervisorCreate"];
export type Internship = Schemas["InternshipRead"];
export type InternshipCreate = Schemas["InternshipCreate"];
export type InternshipStatus = Schemas["InternshipStatus"];
export type Task = Schemas["TaskRead"];
export type TaskCreate = Schemas["TaskCreate"];
export type TaskStatus = Schemas["TaskStatus"];
export type Report = Schemas["ReportRead"];
export type ReportCreate = Schemas["ReportCreate"];
export type StudyLevel = Schemas["StudyLevel"];

export interface Page<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}
