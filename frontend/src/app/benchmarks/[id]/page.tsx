import type { Metadata } from "next";
import { BenchmarkDetailClient } from "./BenchmarkDetailClient";

export const metadata: Metadata = {
  title: "Benchmark Run Details | Rapier Bench",
  description:
    "Detailed evaluation metrics, execution progress, and prediction records.",
};

interface BenchmarkDetailsPageProps {
  params: Promise<{ id: string }>;
}

export default async function BenchmarkDetailsPage({
  params,
}: BenchmarkDetailsPageProps) {
  const { id } = await params;
  return <BenchmarkDetailClient runId={id} />;
}
