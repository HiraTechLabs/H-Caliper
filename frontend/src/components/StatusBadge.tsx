import { statusLabel } from "@/lib/format";

type Tone = "green" | "red" | "amber" | "blue" | "slate" | "violet";

const TONES: Record<Tone, string> = {
  green: "border-emerald-200 bg-emerald-50 text-emerald-700",
  red: "border-red-200 bg-red-50 text-red-700",
  amber: "border-amber-300/70 bg-amber-50 text-amber-800",
  blue: "border-sky-200 bg-sky-50 text-sky-700",
  slate: "border-ink-200 bg-ink-50 text-ink-600",
  violet: "border-violet-200 bg-violet-50 text-violet-700",
};

const DOTS: Record<Tone, string> = {
  green: "bg-emerald-500",
  red: "bg-red-500",
  amber: "bg-amber-500",
  blue: "bg-sky-500",
  slate: "bg-ink-400",
  violet: "bg-violet-500",
};

const STATUS_TONES: Record<string, Tone> = {
  PASSED: "green",
  SUCCEEDED: "green",
  ACCEPTED: "green",
  HEALTHY: "green",
  COMPLETED: "green",
  RELEASE_READY: "green",
  APPROVED: "green",
  ACTIVE: "green",
  ENABLED: "green",
  READY: "green",

  FAILED: "red",
  REJECTED: "red",
  BLOCKED: "red",
  UNREACHABLE: "red",
  AUTH_FAILED: "red",
  ERROR: "red",
  DISABLED: "slate",

  WARNING: "amber",
  DEGRADED: "amber",
  AWAITING_APPROVAL: "amber",
  NEEDS_HUMAN_APPROVAL: "amber",
  PENDING: "amber",
  REPLANNING: "amber",
  PLAN_REVIEW: "amber",

  RUNNING: "blue",
  EXECUTING: "blue",
  PLANNING: "blue",
  CONTEXT_COLLECTION: "blue",
  AUTOMATED_VALIDATION: "blue",
  AI_REVIEW: "violet",
  DOCUMENTATION: "violet",
  DEPLOYING: "blue",
  READY_FOR_EXECUTION: "blue",

  CREATED: "slate",
  CANCELLED: "slate",
  UNKNOWN: "slate",
  NOT_CONFIGURED: "slate",
  SKIPPED: "slate",
  ARCHIVED: "slate",
};

export function statusTone(status: string): Tone {
  return STATUS_TONES[status?.toUpperCase()] ?? "slate";
}

interface StatusBadgeProps {
  status: string;
  label?: string;
  pulse?: boolean;
  showDot?: boolean;
  className?: string;
}

export function StatusBadge({
  status,
  label,
  pulse = false,
  showDot = true,
  className = "",
}: StatusBadgeProps) {
  const tone = statusTone(status);
  return (
    <span className={`chip ${TONES[tone]} ${className}`}>
      {showDot ? (
        <span className={`h-1.5 w-1.5 rounded-full ${DOTS[tone]} ${pulse ? "animate-pulse" : ""}`} />
      ) : null}
      {label ?? statusLabel(status)}
    </span>
  );
}
