"use client";

export type RecordPageSize = 10 | 25 | 50 | "all";

type Props = {
  page: number;
  pageSize: RecordPageSize;
  total: number;
  loading?: boolean;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: RecordPageSize) => void;
};

export default function PaginationControls({ page, pageSize, total, loading = false, onPageChange, onPageSizeChange }: Props) {
  const showingAll = pageSize === "all";
  const pages = showingAll ? 1 : Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="row-between pagination-controls">
      <label className="field">
        Records per page
        <select
          value={pageSize}
          onChange={(event) => onPageSizeChange(event.target.value === "all" ? "all" : Number(event.target.value) as 10 | 25 | 50)}
        >
          <option value={10}>10</option>
          <option value={25}>25</option>
          <option value={50}>50</option>
          <option value="all">All</option>
        </select>
      </label>
      <span className="muted">
        {showingAll ? `Showing all ${total} records` : `Page ${page} of ${pages} · ${total} matching records`}
      </span>
      {!showingAll && (
        <div className="actions">
          <button className="secondary small" disabled={loading || page <= 1} onClick={() => onPageChange(page - 1)}>Previous</button>
          <button className="secondary small" disabled={loading || page >= pages} onClick={() => onPageChange(page + 1)}>Next</button>
        </div>
      )}
    </div>
  );
}
