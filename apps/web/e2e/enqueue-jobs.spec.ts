import { test, expect } from "@playwright/test";

test("enqueue and view jobs", async ({ page }) => {
  await page.goto("/story/2/queue");
  await page.getByTestId("captions-checkbox").check();
  await page.getByRole("button", { name: "Enqueue" }).click();
  await expect(page).toHaveURL(/\/story\/2\/jobs/);
  await expect(page.getByTestId("job-row").first()).toContainText("Queued");
  await page.goto("/jobs");
  await expect(page.getByTestId("job-row").first()).toBeVisible();
});
