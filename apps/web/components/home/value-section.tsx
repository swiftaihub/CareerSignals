import { BrainCircuit, BriefcaseBusiness, ClipboardCheck, GitBranch, LineChart, Target } from "lucide-react";

const values = [
  {
    title: "Signal over noise",
    body: "Prioritize roles by match score, salary context, skill fit, visa signal, work model, and company relevance.",
    icon: Target
  },
  {
    title: "Pipeline-backed intelligence",
    body: "Move from scattered postings to normalized, scored, dashboard-ready records through a repeatable data pipeline.",
    icon: GitBranch
  },
  {
    title: "FastAPI + dbt + MotherDuck architecture",
    body: "Keep secrets server-side while serving clean analytics contracts to a responsive Next.js experience.",
    icon: BrainCircuit
  },
  {
    title: "Daily decision queue for high-fit roles",
    body: "Review the best opportunities first, update application status, and keep a focused application workflow.",
    icon: ClipboardCheck
  }
];

const outcomes = [
  ["Role prioritization", "Focus on the jobs with the strongest evidence of fit."],
  ["Skill-gap clarity", "See which capabilities appear most often in high-value roles."],
  ["Company ranking", "Compare opportunity quality across employers and industries."],
  ["Workflow tracking", "Carry roles from saved to applied to interview without spreadsheet drift."]
];

export function ValueSection() {
  return (
    <section className="mx-auto max-w-7xl px-4 py-16 md:px-6 lg:px-8">
      <div className="grid gap-8 lg:grid-cols-[0.85fr_1.15fr]">
        <div>
          <div className="text-xs font-semibold uppercase text-primary">Enterprise Product Value</div>
          <h2 className="mt-3 text-3xl font-bold text-foreground md:text-4xl">
            A credible analytics layer for job-search decisions.
          </h2>
          <p className="mt-4 text-base leading-7 text-muted-foreground">
            CareerSignal treats job search like a data product: source ingestion, signal extraction,
            score modeling, decision queues, status updates, and exportable reporting.
          </p>
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {outcomes.map(([label, body]) => (
              <div key={label} className="rounded-md border border-border bg-card p-4 shadow-sm">
                <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                  {label === "Skill-gap clarity" ? (
                    <LineChart className="h-4 w-4 text-primary" />
                  ) : (
                    <BriefcaseBusiness className="h-4 w-4 text-primary" />
                  )}
                  {label}
                </div>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{body}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          {values.map((item) => {
            const Icon = item.icon;
            return (
              <article key={item.title} className="rounded-lg border border-border bg-card p-5 shadow-soft">
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-teal-50 text-primary">
                  <Icon className="h-5 w-5" />
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
