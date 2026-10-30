import { LoaderCircle } from "lucide-react";

export function Loading({ label = "Loading", full = false }: { label?: string; full?: boolean }) {
  return (
    <div className={`flex items-center justify-center gap-2 text-sm text-ink-500 ${full ? "min-h-[50vh]" : "py-10"}`}>
      <LoaderCircle className="h-4 w-4 animate-spin text-amber-600" />
      <span>{label}</span>
    </div>
  );
}

export function Skeleton({ className = "h-20" }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />;
}
