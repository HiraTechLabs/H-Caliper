import { ChevronLeft, ChevronRight } from "lucide-react";

export function Pagination({ page, pageSize, total, onChange }: { page: number; pageSize: number; total: number; onChange: (page: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  return <div className="flex flex-wrap items-center justify-between gap-3 border-t border-ink-100 px-4 py-3 text-xs text-ink-500"><span>Showing <b className="font-semibold text-ink-700">{start}–{end}</b> of <b className="font-semibold text-ink-700">{total}</b></span><div className="flex items-center gap-1"><button className="btn-ghost btn-sm" disabled={page <= 1} onClick={() => onChange(page - 1)} aria-label="Previous page"><ChevronLeft className="h-3.5 w-3.5" /></button><span className="px-2">Page {page} of {pages}</span><button className="btn-ghost btn-sm" disabled={page >= pages} onClick={() => onChange(page + 1)} aria-label="Next page"><ChevronRight className="h-3.5 w-3.5" /></button></div></div>;
}
