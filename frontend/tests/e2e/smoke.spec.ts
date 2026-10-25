import { test, expect } from "@playwright/test";

test.skip(!process.env.E2E_BASE_URL, "set E2E_BASE_URL to run e2e");

test("smoke test", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/Rapier Bench/i);
});
