import { describeError } from "../api/problem";

export function ErrorAlert({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <p role="alert" className="alert">
      {describeError(error)}
    </p>
  );
}
