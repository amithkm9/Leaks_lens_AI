import { test, expect } from "@playwright/test";

test("edit source → scan revision → archive → restore → paginate", async ({
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
  await page.getByRole("link", { name: "Sources", exact: true }).click();
  const sources = page.getByRole("region", { name: "Connected sources" });
  await sources
    .getByRole("row")
    .filter({ hasText: "Synthetic editable repository" })
    .getByRole("button", { name: "Edit", exact: true })
    .click();
  const editor = page.getByRole("dialog", { name: "Edit source" });
  await editor.getByLabel("Source name").fill("Updated browser repository");
  await editor.getByLabel("Maximum documents per scan").fill("7");
  await editor.getByRole("checkbox").check();
  await editor.getByRole("button", { name: "Save source" }).click();
  await expect(editor).toBeHidden();
  const row = sources
    .getByRole("row")
    .filter({ hasText: "Updated browser repository" });
  await row.getByRole("button", { name: "Scan", exact: true }).click();
  const scans = page.getByRole("region", { name: "Scan activity" });
  await expect(
    scans.getByRole("row").filter({ hasText: "Source revision 2" }),
  ).toContainText("completed");
  await row.getByRole("button", { name: "Reanalyze", exact: true }).click();
  const reanalysis = page.getByRole("dialog", {
    name: "Reanalyze · Updated browser repository",
  });
  await reanalysis
    .getByLabel("Reanalysis reason")
    .fill("Refresh all available source documents");
  await reanalysis.getByRole("button", { name: "Reanalyze source" }).click();
  await expect(reanalysis).toBeHidden();
  await expect(
    scans
      .getByRole("row")
      .filter({ hasText: "Reanalysis · Refresh all available" }),
  ).toContainText("completed");
  await row.getByRole("button", { name: "Archive", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Source archived");
  await expect(row).toHaveCount(0);
  await page.getByLabel("Source state").selectOption("archived");
  await row.getByRole("button", { name: "Restore", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Source restored");
  await page.getByLabel("Source state").selectOption("active");
  await row.getByRole("button", { name: "History", exact: true }).click();
  const history = page.getByRole("dialog", {
    name: "History · Updated browser repository",
  });
  await expect(
    history.getByText("updated · Revision 2", { exact: true }),
  ).toBeVisible();
  await expect(
    history.getByText("archived · Revision 3", { exact: true }),
  ).toBeVisible();
  await expect(
    history.getByText("restored · Revision 4", { exact: true }),
  ).toBeVisible();
  await expect(
    history.getByText("Updated browser repository · Source revision 2").first(),
  ).toBeVisible();
  await history.getByRole("button", { name: "Close", exact: true }).click();

  // Seed additional sources through the real authenticated API, using the disposable local repository.
  const auth = await (await page.request.get("/api/auth/me")).json();
  const listing = await (
    await page.request.get("/api/sources?q=Updated%20browser")
  ).json();
  for (let n = 0; n < 12; n++) {
    const response = await page.request.post("/api/sources", {
      headers: { "X-CSRF-Token": auth.csrf_token },
      data: {
        name: `Browser page ${String(n).padStart(2, "0")}`,
        kind: "git",
        authorized: true,
        access_context: "authorized_private",
        config: listing.items[0].config,
      },
    });
    expect(response.status()).toBe(201);
  }
  await page.getByLabel("Search sources").fill("Browser page");
  const pagination = page.getByRole("navigation", {
    name: "sources pagination",
    exact: true,
  });
  await expect(pagination).toContainText("1–10 of 12 sources");
  await pagination.getByRole("button", { name: "Next", exact: true }).click();
  await expect(pagination).toContainText("11–12 of 12 sources");
  await expect(sources.getByRole("row")).toHaveCount(3);
  await expect(
    sources.getByText("Browser page 00", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Search sources").fill("Updated browser");
  await expect(row).toBeVisible();
  await page.screenshot({
    path: "test-results/sources-verification.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "test-results/sources-mobile-verification.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
