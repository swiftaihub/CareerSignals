import type { ApiError } from "@/lib/types";

export function ErrorState({
  error,
  title = "Something went wrong"
}: {
  error?: ApiError | Error | unknown;
  title?: string;
}) {
  const message =
    typeof error === "object" && error !== null && "detail" in error
      ? String((error as ApiError).detail)
      : error instanceof Error
        ? error.message
        : "The API request failed. Check that FastAPI is running.";

  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-5 text-sm text-red-900">
      <h3 className="font-semibold">{title}</h3>
      <p className="mt-1">{message}</p>
    </div>
  );
}
