import Link from "next/link";

export function LoadingState({
  message = "Loading benchmark data...",
}: {
  message?: string;
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex min-h-[200px] flex-col items-center justify-center gap-3 p-6 text-zinc-400"
    >
      <svg
        className="h-6 w-6 animate-spin text-indigo-500"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8v8H4z"
        />
      </svg>
      <span className="text-sm">{message}</span>
    </div>
  );
}

export function ErrorState({
  title = "Failed to load data",
  message,
  onRetry,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      aria-live="polite"
      className="rounded-xl border border-red-800/60 bg-red-950/30 p-6 text-center text-red-200"
    >
      <h3 className="text-base font-semibold text-red-100">{title}</h3>
      <p className="mt-1 text-sm text-red-300">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-4 rounded-md border border-red-700 bg-red-900/40 px-3.5 py-1.5 text-xs font-medium text-red-100 hover:bg-red-800/60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-500"
        >
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  message,
  actionHref,
  actionLabel,
}: {
  title: string;
  message: string;
  actionHref?: string;
  actionLabel?: string;
}) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-8 text-center">
      <h3 className="text-base font-semibold text-zinc-200">{title}</h3>
      <p className="mt-1 text-sm text-zinc-400">{message}</p>
      {actionHref && actionLabel && (
        <div className="mt-4">
          <Link
            href={actionHref}
            className="inline-flex items-center rounded-md bg-indigo-600 px-3.5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500"
          >
            {actionLabel}
          </Link>
        </div>
      )}
    </div>
  );
}
