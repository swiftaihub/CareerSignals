import type { ApiError } from "@/lib/types";

export function ErrorState({
  error,
  title = "Something went wrong"
}: {
  error?: ApiError | Error | unknown;
  title?: string;
}) {
  const apiError =
    typeof error === "object" && error !== null && "detail" in error
      ? (error as ApiError)
      : null;
  const message =
    apiError
      ? String(apiError.detail)
      : error instanceof Error
        ? error.message
        : "The API request failed. Check that FastAPI is running.";

  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-5 text-sm text-red-900">
      <h3 className="font-semibold">{title}</h3>
      <p className="mt-1">{message}</p>
      {apiError?.error_code ? (
        <p className="mt-2 text-xs font-medium uppercase tracking-wide text-red-700">
          {apiError.error_code}
          {apiError.status ? ` - HTTP ${apiError.status}` : ""}
        </p>
      ) : null}
    </div>
  );
}
