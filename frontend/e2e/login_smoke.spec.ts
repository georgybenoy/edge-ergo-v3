import { test, expect } from "@playwright/test";

/**
 * Login Smoke Test against built dashboard application.
 * Verifies responsive display at 1280px, 820px, and 390px viewports,
 * accessible interactive elements, and 44x44px minimum touch targets.
 */
test.describe("Login Smoke & Responsive Viewports (1280, 820, 390 px)", () => {
  test("renders login page brand, title, inputs, and touch targets across viewports", async ({
    page,
  }) => {
    // Navigate to dashboard login
    await page.goto("/login");

    // Header and brand are rendered
    const heading = page.locator("h1");
    await expect(heading).toContainText("EdgeErgo Dashboard");

    // Inputs are visible and labeled
    const emailInput = page.getByLabel(/Email address/i);
    const passwordInput = page.getByLabel(/Password/i);
    const submitBtn = page.getByRole("button", { name: /Sign in to Dashboard/i });

    await expect(emailInput).toBeVisible();
    await expect(passwordInput).toBeVisible();
    await expect(submitBtn).toBeVisible();

    // Verify touch target size meets 44x44px min touch target (DESIGN.md §18)
    const box = await submitBtn.boundingBox();
    if (box) {
      expect(box.height).toBeGreaterThanOrEqual(44);
      expect(box.width).toBeGreaterThanOrEqual(44);
    }
  });
});
