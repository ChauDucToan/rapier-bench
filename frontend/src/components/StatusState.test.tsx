import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EmptyState, ErrorState, LoadingState } from "./StatusState";

describe("StatusState components", () => {
  it("renders LoadingState with role=status and aria-live=polite", () => {
    render(<LoadingState message="Fetching benchmark telemetry..." />);
    const statusElem = screen.getByRole("status");
    expect(statusElem).toBeDefined();
    expect(statusElem.getAttribute("aria-live")).toBe("polite");
    expect(screen.getByText("Fetching benchmark telemetry...")).toBeDefined();
  });

  it("renders ErrorState with role=alert and triggers retry callback", () => {
    const handleRetry = vi.fn();
    render(
      <ErrorState
        title="Inference Connection Failed"
        message="Backend GPU runner timed out."
        onRetry={handleRetry}
      />,
    );

    const alertElem = screen.getByRole("alert");
    expect(alertElem).toBeDefined();
    expect(screen.getByText("Inference Connection Failed")).toBeDefined();
    expect(screen.getByText("Backend GPU runner timed out.")).toBeDefined();

    const retryBtn = screen.getByRole("button", { name: /retry/i });
    fireEvent.click(retryBtn);
    expect(handleRetry).toHaveBeenCalledOnce();
  });

  it("renders EmptyState with custom title, message, and action link", () => {
    render(
      <EmptyState
        title="No completed runs"
        message="Launch a benchmark to view results."
        actionHref="/benchmarks/new"
        actionLabel="Start Evaluation"
      />,
    );

    expect(screen.getByText("No completed runs")).toBeDefined();
    expect(
      screen.getByText("Launch a benchmark to view results."),
    ).toBeDefined();
    const actionLink = screen.getByRole("link", { name: /start evaluation/i });
    expect(actionLink.getAttribute("href")).toBe("/benchmarks/new");
  });
});
