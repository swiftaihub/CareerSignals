import { Building2, CalendarCheck2, CheckCircle2, LineChart, ListChecks } from "lucide-react";

const useCases = [
  {
    title: "Daily top-match review",
    body: "Start with the highest-scoring roles and make quick save, apply, or archive decisions.",
    icon: CalendarCheck2
  },
  {
    title: "Skill gap planning",
    body: "Compare recurring job requirements against the candidate profile to choose what to learn next.",
    icon: LineChart
  },
  {
    title: "Company prioritization",
    body: "Rank employers by match quality, role count, salary signal, and industry relevance.",
    icon: Building2
  },
  {
    title: "Application workflow tracking",
    body: "Keep every role moving through saved, applied, interview, offer, rejected, or archived states.",
    icon: ListChecks
  }
];

export function UseCasesSection() {
  return (
    <section className="border-y border-border bg-card/70">
      <div className="mx-auto max-w-7xl px-4 py-16 md:px-6 lg:px-8">
        <div className="max-w-3xl">
          <div className="text-xs font-semibold uppercase text-primary">Use Cases</div>
          <h2 className="mt-3 text-3xl font-bold text-foreground md:text-4xl">
            The daily operating system for a serious job search.
          </h2>
          <p className="mt-4 text-base leading-7 text-muted-foreground">
            CareerSignal keeps the workflow focused: review the right jobs, understand the why,
            update status, and export the latest intelligence when needed.
          </p>
        </div>
        <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {useCases.map((item) => {
            const Icon = item.icon;
            return (
              <article key={item.title} className="rounded-lg border border-border bg-background p-5 shadow-sm">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-md bg-teal-50 text-primary">
                    <Icon className="h-5 w-5" />
                  </div>
                  <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                </div>
                <h3 className="mt-4 text-base font-semibold text-foreground">{item.title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.body}</p>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
