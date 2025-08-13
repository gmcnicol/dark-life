import { test, expect } from "@playwright/test";

test("inbox to review", async ({ page }) => {
  await page.goto("/inbox");
  await page.keyboard.press("j");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/story\/2\/review/);
  await expect(page.getByTestId("status")).toHaveText("Status: pending");
  await page.keyboard.press("A");
  await expect(page.getByTestId("status")).toHaveText("Status: approved");
});
