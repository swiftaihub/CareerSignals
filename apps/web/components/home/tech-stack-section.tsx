const stack = [
  {
    title: "Data Ingestion",
    body: "Python connectors, REST APIs, configurable YAML categories, freshness filtering"
  },
  {
    title: "Processing",
    body: "Normalization, deduplication, salary parsing, skill extraction, visa detection, match scoring"
  },
  {
    title: "Analytics Layer",
    body: "MotherDuck, dbt staging/intermediate/mart models, raw/staging/app schemas"
  },
  {
    title: "Backend",
    body: "FastAPI, Pydantic, repository pattern, local/MotherDuck data modes"
  },
  {
    title: "Frontend",
    body: "Next.js, TypeScript, Tailwind CSS, shadcn-style UI, TanStack Table, Recharts"
  },
  {
    title: "Exports",
    body: "Excel workbook with All Jobs, Top Matches, Category Summary, Skill Gap, and Company Priority tabs"
  },
  {
    title: "Future SaaS",
    body: "Supabase Auth, user profiles, multi-user job matching, hosted deployment"
  }
];

export function TechStackSection() {
  return (
    <section className="border-y border-border bg-card/70">
      <div className="mx-auto max-w-7xl px-4 py-14 md:px-6 lg:px-8">
        <div className="max-w-3xl">
          <div className="text-xs font-semibold uppercase text-primary">Technology Stack</div>
          <h2 className="mt-2 text-3xl font-bold">Built like a data product, not a spreadsheet.</h2>
          <p className="mt-3 text-base leading-7 text-muted-foreground">
            CareerSignal separates ingestion, transformation, serving, and presentation so the
            personal dashboard can grow into a hosted multi-user product later.
          </p>
        </div>
        <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {stack.map((item) => (
            <div key={item.title} className="rounded-lg border border-border bg-background p-5">
              <h3 className="font-semibold">{item.title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
