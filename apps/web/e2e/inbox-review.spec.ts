import { test, expect } from "@playwright/test";

test("inbox to review", async ({ page }) => {
  await page.goto("/inbox");
  await page.keyboard.press("j");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/story\/2\/review/);
  await expect(page.getByTestId("status")).toContainText("Status:");
  await page.getByRole("button", { name: /generate script/i }).click();
  await page.getByRole("button", { name: /approve story/i }).click();
  await expect(page.getByTestId("status")).toHaveText("Status: approved");
  await page.goto("/story/2/split");
  await page.getByRole("button", { name: "Save Parts" }).click();
  await expect(page.getByTestId("status")).toHaveText("Status: approved");
  await page.goto("/story/2/media");
  await page.getByRole("button", { name: "Apply Best Matches" }).click();
  await page.getByRole("button", { name: "Save Bundle" }).click();
  await expect(page.getByTestId("status")).toHaveText("Status: media_ready");
});
