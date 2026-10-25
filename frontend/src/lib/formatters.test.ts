import { describe, expect, it } from "vitest";
import {
  formatDate,
  formatLatency,
  formatMetricName,
  formatMetricValue,
  formatParameters,
  formatVram,
} from "./formatters";

describe("formatters helper", () => {
  describe("formatMetricValue", () => {
    it("formats percentage metrics accurately", () => {
      expect(formatMetricValue("accuracy", 0.852)).toBe("85.2%");
      expect(formatMetricValue("balanced_accuracy", 0.5)).toBe("50.0%");
      expect(formatMetricValue("micro_f1", 0.6667)).toBe("66.7%");
      expect(formatMetricValue("prompt_level_strict_acc", 0.9)).toBe("90.0%");
      expect(formatMetricValue("invalid_parsed_rate", 0.05)).toBe("5.0%");
    });

    it("formats count metrics as whole integers with locale separators", () => {
      expect(formatMetricValue("nn_count", 42)).toBe("42");
      expect(formatMetricValue("sample_count", 1000)).toBe("1,000");
      expect(formatMetricValue("vc_count", 15)).toBe("15");
    });

    it("formats latency and vram metrics with units", () => {
      expect(formatMetricValue("avg_latency_ms", 32.45)).toBe("32.5 ms");
      expect(formatMetricValue("vram_weight_gb", 1.3)).toBe("1.30 GB");
    });

    it("handles null and undefined gracefully", () => {
      expect(formatMetricValue("accuracy", null)).toBe("—");
      expect(formatMetricValue("accuracy", undefined)).toBe("—");
      expect(formatMetricValue("unknown_metric", NaN)).toBe("—");
    });
  });

  describe("formatMetricName", () => {
    it("returns human-readable names for known evaluation metric keys", () => {
      expect(formatMetricName("micro_f1")).toBe("Micro F1");
      expect(formatMetricName("balanced_accuracy")).toBe("Balanced Accuracy");
      expect(formatMetricName("prompt_level_strict_acc")).toBe(
        "Strict Prompt Acc",
      );
      expect(formatMetricName("unanswerable_context_accuracy")).toBe(
        "Unanswerable Acc",
      );
    });

    it("formats unknown snake_case keys cleanly", () => {
      expect(formatMetricName("custom_score_metric")).toBe(
        "Custom Score Metric",
      );
    });
  });

  describe("formatParameters", () => {
    it("formats model parameter counts into millions or billions", () => {
      expect(formatParameters(354483968)).toBe("354M");
      expect(formatParameters(649281964)).toBe("649M");
      expect(formatParameters(1500000000)).toBe("1.5B");
    });

    it("handles 0 or negative numbers", () => {
      expect(formatParameters(0)).toBe("—");
    });
  });

  describe("formatVram & formatLatency", () => {
    it("formats VRAM with two decimals and GB unit", () => {
      expect(formatVram(1.15)).toBe("1.15 GB");
      expect(formatVram(null)).toBe("—");
    });

    it("formats latency with one decimal and ms unit", () => {
      expect(formatLatency(45.24)).toBe("45.2 ms");
      expect(formatLatency(null)).toBe("—");
    });
  });

  describe("formatDate", () => {
    it("formats valid ISO strings", () => {
      const formatted = formatDate("2026-10-26T12:00:00Z");
      expect(formatted).not.toBe("—");
      expect(formatted.length).toBeGreaterThan(0);
    });

    it("handles null or undefined dates", () => {
      expect(formatDate(null)).toBe("—");
    });
  });
});
