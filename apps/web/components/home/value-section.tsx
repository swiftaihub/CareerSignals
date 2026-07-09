import { BriefcaseBusiness, ClipboardCheck, Clock, LineChart, Target, Trophy } from "lucide-react";

const values = [
  {
    title: "Prioritize Better",
    body: "Rank roles by match score, salary, skills, industry, visa signal, and work arrangement.",
    icon: Target
  },
  {
    title: "Save Time",
    body: "Replace repetitive spreadsheet tracking with automated ingestion, scoring, dashboarding, and Excel export.",
    icon: Clock
  },
  {
    title: "Identify Skill Gaps",
    body: "Compare real job descriptions against your profile to identify high-value skills to improve.",
    icon: LineChart
  },
  {
    title: "Track Applications",
    body: "Manage saved, applied, interview, rejected, offer, and archived roles in one workflow.",
    icon: ClipboardCheck
  },
  {
    title: "Build Career Intelligence",
    body: "Analyze category trends, salary ranges, company opportunity quality, visa signals, and role-fit patterns over time.",
    icon: BriefcaseBusiness
  },
  {
    title: "Showcase Data Product Skills",
    body: "Demonstrate end-to-end analytics engineering across APIs, Python, MotherDuck, dbt, FastAPI, Next.js, and Excel reporting.",
    icon: Trophy
  }
];

export function ValueSection() {
  return (
    <section className="mx-auto max-w-7xl px-4 py-14 md:px-6 lg:px-8">
      <div className="grid gap-5 lg:grid-cols-2">
        <div className="rounded-lg border border-border bg-card p-6 shadow-soft">
          <div className="text-xs font-semibold uppercase text-primary">Problem</div>
          <p className="mt-3 text-lg leading-8 text-muted-foreground">
            Modern job search is fragmented across job boards, company career pages,
            recruiters, and spreadsheets. High-fit roles are easy to miss, job descriptions
            are messy and inconsistent, and manual tracking makes it difficult to prioritize
            applications strategically.
          </p>
        </div>
        <div className="rounded-lg border border-border bg-card p-6 shadow-soft">
          <div className="text-xs font-semibold uppercase text-primary">Solution</div>
          <p className="mt-3 text-lg leading-8 text-muted-foreground">
            CareerSignal ingests postings through configurable connectors, normalizes messy
            source data, extracts salary, skill, visa, and work-arrangement signals, scores
            each role against a candidate profile, and publishes dashboard-ready mart tables
            through a MotherDuck plus dbt analytics layer.
          </p>
        </div>
      </div>

      <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {values.map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.title} className="rounded-lg border border-border bg-card p-5 shadow-soft">
              <div className="flex h-10 w-10 items-center justify-center rounded-md bg-teal-50 text-primary">
                <Icon className="h-5 w-5" />
              </div>
              <h3 className="mt-4 text-base font-semibold">{item.title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.body}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
