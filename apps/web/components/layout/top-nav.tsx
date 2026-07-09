import Link from "next/link";
import { ExternalLink } from "lucide-react";

export function TopNav() {
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-background/85 px-4 py-3 backdrop-blur md:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase text-muted-foreground">
            CareerSignal Personal Dashboard
          </div>
          <div className="text-sm text-muted-foreground">
            FastAPI service layer over local or MotherDuck-backed analytics data
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Link className="btn btn-ghost lg:hidden" href="/">
            Home
          </Link>
          <Link className="btn btn-primary" href="/jobs">
            Explore Jobs
            <ExternalLink className="h-4 w-4" />
          </Link>
        </div>
      </div>
    </header>
  );
}
