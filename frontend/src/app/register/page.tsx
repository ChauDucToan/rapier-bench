"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { useAuth } from "@/features/auth";

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuth();

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setServerError(null);

    const errors: Record<string, string> = {};
    if (!username.trim()) {
      errors.username = "Username is required";
    } else if (username.trim().length < 3) {
      errors.username = "Username must be at least 3 characters";
    } else if (username.trim().length > 64) {
      errors.username = "Username must be 64 characters or less";
    }

    if (!email.trim()) {
      errors.email = "Email is required";
    } else if (!email.includes("@")) {
      errors.email = "Please enter a valid email address";
    }

    if (!password) {
      errors.password = "Password is required";
    } else if (password.length < 6) {
      errors.password = "Password must be at least 6 characters";
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }
    setFieldErrors({});

    setSubmitting(true);
    try {
      await register({
        username: username.trim(),
        email: email.trim(),
        password,
      });
      router.push("/dashboard");
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Registration failed";
      setServerError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-md py-8">
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-6 sm:p-8">
        <h1 className="text-2xl font-bold tracking-tight text-white">
          Create Account
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Register to launch benchmarks and store evaluation histories.
        </p>

        {serverError && (
          <div
            role="alert"
            aria-live="polite"
            className="mt-4 rounded-md border border-red-800/60 bg-red-950/40 p-3 text-sm text-red-300"
          >
            {serverError}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-6 space-y-4" noValidate>
          <div>
            <label
              htmlFor="username"
              className="block text-xs font-medium text-zinc-300"
            >
              Username
            </label>
            <input
              id="username"
              name="username"
              type="text"
              autoComplete="username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              aria-invalid={Boolean(fieldErrors.username)}
              aria-describedby={
                fieldErrors.username ? "username-error" : undefined
              }
              className="mt-1.5 block w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              placeholder="researcher1"
            />
            {fieldErrors.username && (
              <p id="username-error" className="mt-1 text-xs text-red-400">
                {fieldErrors.username}
              </p>
            )}
          </div>

          <div>
            <label
              htmlFor="email"
              className="block text-xs font-medium text-zinc-300"
            >
              Email address
            </label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              aria-invalid={Boolean(fieldErrors.email)}
              aria-describedby={fieldErrors.email ? "email-error" : undefined}
              className="mt-1.5 block w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              placeholder="user@example.com"
            />
            {fieldErrors.email && (
              <p id="email-error" className="mt-1 text-xs text-red-400">
                {fieldErrors.email}
              </p>
            )}
          </div>

          <div>
            <label
              htmlFor="password"
              className="block text-xs font-medium text-zinc-300"
            >
              Password (min 6 characters)
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="new-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-invalid={Boolean(fieldErrors.password)}
              aria-describedby={
                fieldErrors.password ? "password-error" : undefined
              }
              className="mt-1.5 block w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              placeholder="••••••••"
            />
            {fieldErrors.password && (
              <p id="password-error" className="mt-1 text-xs text-red-400">
                {fieldErrors.password}
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? "Creating account..." : "Register"}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-zinc-400">
          Already have an account?{" "}
          <Link
            href="/login"
            className="font-medium text-indigo-400 hover:text-indigo-300 focus-visible:outline-2 focus-visible:outline-indigo-500 rounded"
          >
            Sign In
          </Link>
        </p>
      </div>
    </div>
  );
}
