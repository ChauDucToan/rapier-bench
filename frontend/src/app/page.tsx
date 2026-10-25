import Link from "next/link";

export default function HomePage() {
  return (
    <section className="flex flex-col items-center justify-center py-16 text-center sm:py-24">
      <h1 className="text-4xl font-extrabold tracking-tight text-white sm:text-5xl md:text-6xl">
        Rapier Bench
      </h1>
      <p className="mx-auto mt-6 max-w-2xl text-lg text-zinc-300">
        A domain-aware AI benchmarking platform engineered for empirical
        evaluation of language models across specialized task accuracy,
        reasoning rigor, and computational efficiency.
      </p>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
        <Link
          href="/benchmarks/new"
          className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500"
        >
          New Benchmark
        </Link>
        <Link
          href="/dashboard"
          className="rounded-lg border border-zinc-700 bg-zinc-900 px-5 py-2.5 text-sm font-semibold text-zinc-200 transition hover:bg-zinc-800 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-400"
        >
          Go to Dashboard
        </Link>
      </div>

      <div className="mt-16 grid w-full max-w-4xl grid-cols-1 gap-6 text-left sm:grid-cols-3">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-6">
          <h2 className="text-base font-semibold text-white">
            Domain-Tailored Evaluation
          </h2>
          <p className="mt-2 text-sm text-zinc-400">
            Execute specialized benchmark suites configured against targeted
            domain datasets and domain-specific validation metrics.
          </p>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-6">
          <h2 className="text-base font-semibold text-white">
            Head-to-Head Comparison
          </h2>
          <p className="mt-2 text-sm text-zinc-400">
            Compare model performance profiles side by side across latency,
            throughput, accuracy distributions, and regression bounds.
          </p>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-6">
          <h2 className="text-base font-semibold text-white">
            Model Recommendation
          </h2>
          <p className="mt-2 text-sm text-zinc-400">
            Derive data-driven model selections mapped to your explicit latency
            ceilings, budget envelopes, and domain accuracy targets.
          </p>
        </div>
      </div>
    </section>
  );
}
