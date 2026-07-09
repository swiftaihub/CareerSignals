import { CheckCircle2 } from "lucide-react";

const useCases = [
  "Personal job-search command center",
  "Career analytics portfolio project",
  "Open-source job intelligence toolkit",
  "University career-services dashboard",
  "Career coach opportunity-tracking workspace",
  "Future SaaS product for job seekers"
];

export function UseCasesSection() {
  return (
    <section className="border-y border-border bg-card/70">
      <div className="mx-auto max-w-7xl px-4 py-14 md:px-6 lg:px-8">
        <div className="max-w-3xl">
          <div className="text-xs font-semibold uppercase text-primary">Use Cases</div>
          <h2 className="mt-2 text-3xl font-bold">Useful today, extensible tomorrow.</h2>
          <p className="mt-3 text-base leading-7 text-muted-foreground">
            The current product is a personal dashboard, but the architecture leaves room for
            authentication, user profiles, hosted refreshes, and multi-user job matching.
          </p>
        </div>
        <div className="mt-8 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {useCases.map((item) => (
            <div key={item} className="flex items-center gap-3 rounded-lg border border-border bg-background p-4">
              <CheckCircle2 className="h-5 w-5 text-primary" />
              <span className="text-sm font-medium">{item}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
