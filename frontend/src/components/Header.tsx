"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/features/auth";

const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/models", label: "Models" },
  { href: "/datasets", label: "Datasets" },
  { href: "/benchmarks", label: "Runs" },
  { href: "/compare", label: "Compare" },
  { href: "/leaderboard", label: "Leaderboard" },
  { href: "/recommend", label: "Recommend" },
  { href: "/history", label: "History" },
];

export function Header() {
  const pathname = usePathname();
  const { user, loading, logout } = useAuth();

  return (
    <header className="sticky top-0 z-50 border-b border-zinc-800 bg-zinc-950/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6 lg:px-8">
        <Link
          href="/"
          className="text-lg font-bold tracking-tight text-white hover:text-zinc-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500 rounded"
        >
          Rapier Bench
        </Link>

        <nav
          aria-label="Main Navigation"
          className="flex flex-wrap items-center gap-1 text-sm font-medium text-zinc-400"
        >
          {NAV_LINKS.map((link) => {
            const isActive =
              pathname === link.href ||
              (link.href !== "/" && pathname.startsWith(`${link.href}/`));
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`rounded px-2.5 py-1.5 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500 ${
                  isActive
                    ? "bg-zinc-800 text-white font-semibold"
                    : "hover:text-zinc-100"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-2 text-sm">
          {loading ? (
            <span className="text-xs text-zinc-500">Checking session...</span>
          ) : user ? (
            <div className="flex items-center gap-3">
              <Link
                href="/profile"
                className="text-xs text-zinc-300 hover:text-white underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-indigo-500 rounded"
              >
                {user.username}
              </Link>
              <button
                type="button"
                onClick={() => void logout()}
                className="rounded border border-zinc-700 bg-zinc-900 px-2.5 py-1 text-xs text-zinc-300 hover:bg-zinc-800 hover:text-white focus-visible:outline-2 focus-visible:outline-indigo-500"
              >
                Sign out
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Link
                href="/login"
                className="rounded px-2.5 py-1 text-xs text-zinc-300 hover:text-white focus-visible:outline-2 focus-visible:outline-indigo-500"
              >
                Sign In
              </Link>
              <Link
                href="/register"
                className="rounded bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-indigo-500 focus-visible:outline-2 focus-visible:outline-indigo-500"
              >
                Register
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
