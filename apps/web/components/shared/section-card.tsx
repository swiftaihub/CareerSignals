import type { ReactNode } from "react";
import { ChevronDown } from "lucide-react";

import { cn } from "@/lib/utils";

interface SectionCardProps {
  title?: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  collapsible?: boolean;
  defaultOpen?: boolean;
}

export function SectionCard({
  title,
  description,
  action,
  children,
  className,
  collapsible = false,
  defaultOpen = true
}: SectionCardProps) {
  if (collapsible) {
    return (
      <section className={cn("rounded-lg border border-border bg-card shadow-soft", className)}>
        <details className="group" open={defaultOpen}>
          <summary className="flex cursor-pointer list-none items-start justify-between gap-4 rounded-lg p-5 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-inset">
            <div>
              {title ? <h2 className="text-base font-semibold text-foreground">{title}</h2> : null}
              {description ? <p className="mt-1 text-sm text-muted-foreground">{description}</p> : null}
            </div>
            <ChevronDown className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground transition group-open:rotate-180 motion-reduce:transition-none" aria-hidden="true" />
          </summary>
          <div className="border-t border-border p-5">{children}</div>
        </details>
      </section>
    );
  }
  return (
    <section className={cn("rounded-lg border border-border bg-card p-5 shadow-soft", className)}>
      {(title || description || action) && (
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            {title ? <h2 className="text-base font-semibold text-foreground">{title}</h2> : null}
            {description ? (
              <p className="mt-1 text-sm text-muted-foreground">{description}</p>
            ) : null}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
