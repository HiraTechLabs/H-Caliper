import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";

type Tone = "success" | "error" | "info";

interface ToastInput {
  title: string;
  description?: string;
  tone?: Tone;
}

interface ToastItem extends ToastInput {
  id: number;
}

interface ToastContextValue {
  toast: (input: ToastInput) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);
const ICONS = { success: CheckCircle2, error: AlertTriangle, info: Info };

const CARD_STYLES: Record<Tone, string> = {
  success: "border-emerald-200 bg-white text-emerald-800",
  error: "border-red-200 bg-white text-red-800",
  info: "border-ink-200 bg-white text-ink-800",
};

const ICON_STYLES: Record<Tone, string> = {
  success: "text-emerald-600",
  error: "text-red-600",
  info: "text-amber-600",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setItems((current) => current.filter((item) => item.id !== id));
  }, []);

  const toast = useCallback(
    (input: ToastInput) => {
      const id = nextId.current++;
      setItems((current) => [...current.slice(-3), { ...input, id }]);
      window.setTimeout(() => dismiss(id), 6000);
    },
    [dismiss],
  );

  const value = useMemo(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        className="pointer-events-none fixed bottom-5 right-5 z-[100] flex w-[min(92vw,380px)] flex-col gap-2"
        aria-live="polite"
        aria-atomic="false"
      >
        {items.map((item) => {
          const tone = item.tone ?? "info";
          const Icon = ICONS[tone];
          return (
            <div
              key={item.id}
              className={`pointer-events-auto flex animate-fade-in items-start gap-3 rounded-xl border px-4 py-3 shadow-lift ${CARD_STYLES[tone]}`}
              role="status"
            >
              <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${ICON_STYLES[tone]}`} aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold">{item.title}</p>
                {item.description ? (
                  <p className="mt-0.5 break-words text-xs leading-5 text-ink-600">
                    {item.description}
                  </p>
                ) : null}
              </div>
              <button
                type="button"
                onClick={() => dismiss(item.id)}
                className="rounded p-0.5 text-ink-400 transition hover:bg-ink-100 hover:text-ink-700"
                aria-label="Dismiss notification"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used inside ToastProvider");
  return context;
}
