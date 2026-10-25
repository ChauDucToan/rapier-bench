"use client";

import { RequireAuth, useAuth } from "@/features/auth";
import { formatDate } from "@/lib/formatters";

export default function ProfilePage() {
  const { user, logout } = useAuth();

  return (
    <RequireAuth>
      <div className="mx-auto max-w-2xl py-6">
        <h1 className="text-2xl font-bold tracking-tight text-white">
          User Profile
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Account details and authentication session status.
        </p>

        {user && (
          <div className="mt-6 rounded-xl border border-zinc-800 bg-zinc-900/60 p-6">
            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-4">
                <dt className="text-xs font-medium text-zinc-400">User ID</dt>
                <dd className="mt-1 text-base font-semibold text-white">
                  #{user.id}
                </dd>
              </div>

              <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-4">
                <dt className="text-xs font-medium text-zinc-400">Username</dt>
                <dd className="mt-1 text-base font-semibold text-white">
                  {user.username}
                </dd>
              </div>

              <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-4">
                <dt className="text-xs font-medium text-zinc-400">Email</dt>
                <dd className="mt-1 text-base font-semibold text-white">
                  {user.email}
                </dd>
              </div>

              <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-4">
                <dt className="text-xs font-medium text-zinc-400">Member Since</dt>
                <dd className="mt-1 text-base font-semibold text-white">
                  {formatDate(user.created_at)}
                </dd>
              </div>
            </dl>

            <div className="mt-6 flex justify-end border-t border-zinc-800 pt-6">
              <button
                type="button"
                onClick={() => void logout()}
                className="rounded-md border border-zinc-700 bg-zinc-800 px-4 py-2 text-sm font-medium text-zinc-200 shadow-sm transition hover:bg-zinc-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500"
              >
                Sign Out
              </button>
            </div>
          </div>
        )}
      </div>
    </RequireAuth>
  );
}
