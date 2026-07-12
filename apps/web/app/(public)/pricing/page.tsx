import Link from "next/link";
import { CheckCircle2 } from "lucide-react";

const features = ["Personal matching and ranking", "Job Explorer and application tracking", "Skill-gap and company analysis", "Scheduled shared job-data refresh", "User-scoped Excel exports"];

export default function PricingPage() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-16 md:px-6 lg:px-8">
      <div className="mx-auto max-w-2xl text-center">
        <div className="text-xs font-semibold uppercase text-primary">Simple access</div>
        <h1 className="mt-3 text-4xl font-bold">Career intelligence for $5 per month</h1>
        <p className="mt-4 text-muted-foreground">Accounts receive a 30-day entitlement when activated. Billing automation is planned; current activation is managed by an administrator.</p>
      </div>
      <div className="mx-auto mt-10 max-w-lg rounded-xl border border-border bg-card p-7 shadow-soft">
        <div className="text-3xl font-bold">$5 <span className="text-base font-normal text-muted-foreground">/ 30 days</span></div>
        <ul className="mt-6 space-y-3">{features.map((feature) => <li key={feature} className="flex gap-2 text-sm"><CheckCircle2 className="h-5 w-5 text-emerald-600" />{feature}</li>)}</ul>
        <Link className="btn btn-primary mt-7 w-full" href="/register">Register for access</Link>
      </div>
    </main>
  );
}
