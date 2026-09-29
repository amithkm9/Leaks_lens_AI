import { test, expect } from "@playwright/test";

test("organization → upload → scan → review → export → recheck", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill("browser@example.test");
  await page
    .getByLabel("Password", { exact: true })
    .fill("Synthetic-browser-only-123");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "A clearer view of exposure." }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await page.getByRole("button", { name: "Add organization" }).click();
  await page.getByLabel("Canonical name").fill("Synthetic Test Organization");
  await page.getByLabel("Exact domains").fill("synthetic-company.test");
  await page.getByRole("button", { name: "Save organization" }).click();
  await expect(
    page.getByRole("heading", { name: "Synthetic Test Organization" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Sources", exact: true }).click();
  await page
    .getByLabel("Upload document", { exact: true })
    .setInputFiles({
      name: "synthetic-test.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(
        "SYNTHETIC TEST DATA\ncompany,email,api_key\nSynthetic Test Organization,person@synthetic-company.test,synthetic-browser-secret-123456\n",
      ),
    });
  await expect(page.getByRole("status")).toContainText("Upload accepted");
  await expect(page.getByText("1 / 1 documents")).toBeVisible();
  await page.getByRole("link", { name: "Incidents", exact: true }).click();
  await page
    .getByRole("link", { name: "Review synthetic-test.csv", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Redacted evidence" }),
  ).toBeVisible();
  await expect(
    page.getByText("synthetic-browser-secret-123456", { exact: false }),
  ).toHaveCount(0);
  await page
    .getByLabel("Reason", { exact: true })
    .fill("Synthetic evidence reviewed in an automated browser test.");
  await page.getByRole("button", { name: "Save review" }).click();
  await expect(page.getByRole("status")).toContainText("Review recorded");
  await expect(page.locator(".badge.confirmed")).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Export JSON" }).click();
  const download = await downloadPromise;
  const stream = await download.createReadStream();
  let body = "";
  for await (const chunk of stream!) body += chunk.toString();
  expect(JSON.parse(body).report.status).toBe("confirmed");
  expect(body).not.toContain("synthetic-browser-secret-123456");
  await page
    .getByRole("button", { name: "Recheck source", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("Source recheck queued");
  await page.getByRole("button", { name: "Run offline assessment" }).click();
  await expect(page.getByText("LLM disabled", { exact: true })).toBeVisible();
  await page.screenshot({
    path: "test-results/incident-verification.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await page.screenshot({
    path: "test-results/overview-verification.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("heading", { name: "A clearer view of exposure." }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "test-results/mobile-verification.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
