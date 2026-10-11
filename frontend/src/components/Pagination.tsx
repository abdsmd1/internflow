interface Props {
  offset: number;
  limit: number;
  total: number;
  onChange: (offset: number) => void;
}

export function Pagination({ offset, limit, total, onChange }: Props) {
  if (total <= limit) return null;
  const last = Math.min(offset + limit, total);
  return (
    <nav className="pagination" aria-label="Pagination">
      <button
        type="button"
        className="button button--quiet"
        disabled={offset === 0}
        onClick={() => {
          onChange(Math.max(0, offset - limit));
        }}
      >
        Précédent
      </button>
      <span>
        {offset + 1}–{last} sur {total}
      </span>
      <button
        type="button"
        className="button button--quiet"
        disabled={last >= total}
        onClick={() => {
          onChange(offset + limit);
        }}
      >
        Suivant
      </button>
    </nav>
  );
}
