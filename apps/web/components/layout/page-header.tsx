import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  description,
  action
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="max-w-3xl">
        {eyebrow ? (
          <div className="text-xs font-semibold uppercase text-primary">{eyebrow}</div>
        ) : null}
        <h1 className="mt-1 text-2xl font-bold text-foreground md:text-3xl">{title}</h1>
        {description ? (
          <p className="mt-2 text-sm leading-6 text-muted-foreground md:text-base">
            {description}
          </p>
        ) : null}
      </div>
      {action}
    </div>
  );
}
