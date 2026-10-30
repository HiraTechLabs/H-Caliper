import type { ComponentType, ReactNode } from "react";
import type { LucideProps } from "lucide-react";
import { Inbox } from "lucide-react";

interface EmptyStateProps {
  icon?: ComponentType<LucideProps>;
  title: string;
  description?: string;
  action?: ReactNode;
  compact?: boolean;
}

export function EmptyState({ icon: Icon = Inbox, title, description, action, compact }: EmptyStateProps) {
  return (
    <div className={`flex flex-col items-center justify-center text-center ${compact ? "py-8" : "py-14"}`}>
      <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-xl border border-ink-200 bg-ink-50 text-ink-400">
        <Icon className="h-5 w-5" aria-hidden />
      </div>
      <p className="text-sm font-semibold text-ink-800">{title}</p>
      {description ? (
        <p className="mt-1 max-w-md text-xs leading-5 text-ink-500">{description}</p>
      ) : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}
