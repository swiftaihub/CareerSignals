import { ArrowRight, ShieldCheck } from "lucide-react";

const flow = [
  "Connector APIs",
  "Raw ingestion",
  "dbt models",
  "FastAPI",
  "Next.js dashboard",
  "Excel/export"
];

export function ArchitectureSection() {
  return (
    <section className="mx-auto max-w-7xl px-4 py-16 md:px-6 lg:px-8">
      <div className="grid gap-8 lg:grid-cols-[0.75fr_1.25fr] lg:items-start">
        <div>
          <div className="text-xs font-semibold uppercase text-primary">Architecture Story</div>
          <h2 className="mt-3 text-3xl font-bold text-foreground md:text-4xl">
            A clean path from noisy postings to trusted decisions.
          </h2>
          <p className="mt-4 text-base leading-7 text-muted-foreground">
            The dashboard never reaches into MotherDuck, local workbooks, or secrets. FastAPI owns
            the service boundary and returns product-ready data contracts to the frontend.
          </p>
          <div className="mt-6 rounded-md border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
            <div className="flex items-center gap-2 font-semibold">
              <ShieldCheck className="h-4 w-4" />
              Secrets stay server-side
            </div>
            <p className="mt-2 leading-6">
              Next.js calls FastAPI only. MotherDuck tokens, filesystem access, dbt execution,
              and exports remain behind the backend layer.
            </p>
          </div>
        </div>

        <div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {flow.map((item, index) => (
              <div key={item} className="relative rounded-md border border-border bg-card p-4 shadow-sm">
                <div className="text-xs font-semibold text-muted-foreground">Step {index + 1}</div>
                <div className="mt-2 min-h-12 text-base font-semibold text-foreground">{item}</div>
                {index < flow.length - 1 ? (
                  <ArrowRight className="absolute -right-4 top-1/2 hidden h-5 w-5 -translate-y-1/2 text-muted-foreground xl:block" />
                ) : null}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
