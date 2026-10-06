export function Pagination({
  data,
  offset,
  onChange,
  label,
}: {
  data: { total: number; items: unknown[]; limit: number } | null;
  offset: number;
  onChange: (offset: number) => void;
  label: string;
}) {
  if (!data || !data.total) return null;
  return (
    <nav className="pagination" aria-label={`${label} pagination`}>
      <span>
        {offset + 1}–{offset + data.items.length} of {data.total} {label}
      </span>
      <div>
        <button
          className="secondary small-button"
          disabled={offset === 0}
          onClick={() => onChange(Math.max(0, offset - data.limit))}
        >
          Previous
        </button>
        <button
          className="secondary small-button"
          disabled={offset + data.limit >= data.total}
          onClick={() => onChange(offset + data.limit)}
        >
          Next
        </button>
      </div>
    </nav>
  );
}
