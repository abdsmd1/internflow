import { useIntern, useSupervisor } from "../api/queries";
import { fullName } from "../lib/format";

// Les stages ne contiennent que des identifiants : on affiche le nom, mis en cache.
export function InternName({ id }: { id: string }) {
  const { data } = useIntern(id);
  return <>{data ? fullName(data) : "…"}</>;
}

export function SupervisorName({ id }: { id: string }) {
  const { data } = useSupervisor(id);
  return <>{data ? fullName(data) : "…"}</>;
}
