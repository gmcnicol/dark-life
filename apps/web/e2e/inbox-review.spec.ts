import { test, expect } from "@playwright/test";

test("inbox to review", async ({ page }) => {
  await page.goto("/inbox");
  await page.keyboard.press("j");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/story\/2\/review/);
  await expect(page.getByTestId("status")).toHaveText("Status: pending");
  await page.keyboard.press("A");
  await expect(page.getByTestId("status")).toHaveText("Status: approved");
  await page.goto("/story/2/split");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByTestId("status")).toHaveText("Status: split");
  await page.goto("/story/2/media");
  await page.getByTestId("catalog-img-0").click();
  await page.getByRole("button", { name: "Apply to all" }).click();
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByTestId("status")).toHaveText(
    "Status: media_selected",
  );
});
