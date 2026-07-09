import { ArrowRight } from "lucide-react";

const flow = [
  "Connector APIs",
  "Raw Job Payloads",
  "Python Processing and Scoring",
  "MotherDuck Raw/Staging Tables",
  "dbt Mart Models",
  "FastAPI Repository Layer",
  "Next.js Dashboard",
  "Excel Export"
];

export function ArchitectureSection() {
  return (
    <section className="mx-auto max-w-7xl px-4 py-14 md:px-6 lg:px-8">
      <div className="max-w-3xl">
        <div className="text-xs font-semibold uppercase text-primary">Architecture</div>
        <h2 className="mt-2 text-3xl font-bold">A clean path from noisy postings to decisions.</h2>
        <p className="mt-3 text-base leading-7 text-muted-foreground">
          The dashboard never talks to MotherDuck directly. FastAPI owns repository access,
          credentials stay server-side, and local mode remains available for offline development.
        </p>
      </div>

      <div className="mt-8 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {flow.map((item, index) => (
          <div key={item} className="relative rounded-lg border border-border bg-card p-4 shadow-soft">
            <div className="text-xs font-semibold text-muted-foreground">Step {index + 1}</div>
            <div className="mt-2 min-h-12 text-base font-semibold">{item}</div>
            {index < flow.length - 1 ? (
              <ArrowRight className="absolute -right-5 top-1/2 hidden h-5 w-5 -translate-y-1/2 text-muted-foreground xl:block" />
            ) : null}
          </div>
        ))}
      </div>
    </section>
  );
}
