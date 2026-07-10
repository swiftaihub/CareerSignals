const stack = [
  {
    title: "Connector APIs",
    body: "Configurable job sources collect raw postings without hardcoding a single board or employer."
  },
  {
    title: "Python signal extraction",
    body: "Normalization, deduplication, salary parsing, skills, seniority, visa signal, and work-arrangement detection."
  },
  {
    title: "dbt mart models",
    body: "Scored jobs, top matches, category summaries, skill gaps, and company priority lists are modeled for reuse."
  },
  {
    title: "FastAPI service layer",
    body: "The browser calls only FastAPI, preserving the boundary around MotherDuck, local files, and secrets."
  },
  {
    title: "Next.js dashboard",
    body: "A responsive product surface supports review, filtering, detail inspection, and application status updates."
  },
  {
    title: "Excel export",
    body: "Decision-ready workbook output keeps the workflow portable for offline review or sharing."
  }
];

export function TechStackSection() {
  return (
    <section className="border-y border-border bg-card/70">
      <div className="mx-auto max-w-7xl px-4 py-16 md:px-6 lg:px-8">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div className="max-w-3xl">
            <div className="text-xs font-semibold uppercase text-primary">Product Architecture</div>
            <h2 className="mt-3 text-3xl font-bold text-foreground md:text-4xl">
              Built as a governed dashboard, not a browser-side script.
            </h2>
            <p className="mt-4 text-base leading-7 text-muted-foreground">
              Each layer has a clear responsibility, making the MVP credible today and extensible
              for hosted refreshes, multi-user profiles, and richer matching later.
            </p>
          </div>
          <div className="rounded-md border border-teal-200 bg-teal-50 px-4 py-3 text-sm font-semibold text-teal-900">
            Frontend to FastAPI to Repository to Data layer
          </div>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {stack.map((item) => (
            <article key={item.title} className="rounded-lg border border-border bg-background p-5 shadow-sm">
              <h3 className="font-semibold text-foreground">{item.title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
