export function LoadingState({ label = "Loading dashboard data..." }: { label?: string }) {
  return (
    <div className="flex min-h-48 items-center justify-center rounded-lg border border-dashed border-border bg-card/70 p-8 text-sm text-muted-foreground">
      <div className="mr-3 h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      {label}
    </div>
  );
}
