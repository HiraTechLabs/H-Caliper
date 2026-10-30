import type { ReactNode } from "react";

interface SectionProps {
  title?: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  padded?: boolean;
}

export function Section({
  title,
  description,
  actions,
  children,
  className = "",
  padded = true,
}: SectionProps) {
  return (
    <section className={`card ${className}`}>
      {title || actions ? (
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-ink-100 px-5 py-3.5">
          <div>
            {title ? <h2 className="text-sm font-bold text-ink-950">{title}</h2> : null}
            {description ? (
              <p className="mt-0.5 text-xs leading-5 text-ink-500">{description}</p>
            ) : null}
          </div>
          {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
        </div>
      ) : null}
      <div className={padded ? "p-5" : ""}>{children}</div>
    </section>
  );
}
