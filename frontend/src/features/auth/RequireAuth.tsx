"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useAuth } from "./AuthContext";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div
        className="flex min-h-[300px] items-center justify-center"
        role="status"
        aria-live="polite"
      >
        <div className="flex items-center gap-3 text-sm text-zinc-400">
          <svg
            className="h-5 w-5 animate-spin text-indigo-500"
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
          <span>Authenticating...</span>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div
        className="mx-auto max-w-md rounded-xl border border-zinc-800 bg-zinc-900/60 p-8 text-center"
        role="alert"
        aria-live="polite"
      >
        <h2 className="text-lg font-semibold text-zinc-100">
          Sign In Required
        </h2>
        <p className="mt-2 text-sm text-zinc-400">
          You must be signed in to access this benchmark feature.
        </p>
        <div className="mt-6 flex items-center justify-center gap-3">
          <Link
            href="/login"
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500"
          >
            Sign In
          </Link>
          <Link
            href="/register"
            className="rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-2 text-sm font-medium text-zinc-200 transition hover:bg-zinc-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500"
          >
            Register
          </Link>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
