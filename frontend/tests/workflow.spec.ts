import { test, expect, type Page, type Route } from "@playwright/test";

async function signIn(page: Page) {
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill("browser@example.test");
  await page
    .getByLabel("Password", { exact: true })
    .fill("Synthetic-browser-only-123");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "A clearer view of exposure." }),
  ).toBeVisible();
}

async function uploadCase(page: Page) {
  const auth = await (await page.request.get("/api/auth/me")).json();
  const upload = await page.request.post("/api/uploads", {
    headers: { "X-CSRF-Token": auth.csrf_token },
    multipart: {
      file: {
        name: "workflow-review.env",
        mimeType: "text/plain",
        buffer: Buffer.from(
          "SYNTHETIC WORKFLOW\napi_key=synthetic-workflow-secret-123456 contact=workflow@company.test\n",
        ),
      },
    },
  });
  expect(upload.status()).toBe(202);
  await expect
    .poll(
      async () =>
        (
          await (
            await page.request.get(`/api/scans/${(await upload.json()).id}`)
          ).json()
        ).processed,
    )
    .toBe(1);
  return (
    await (await page.request.get("/api/incidents?q=workflow-review")).json()
  ).items[0];
}

test("incident filters survive refresh, review navigation, and browser history", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await signIn(page);
  const incident = await uploadCase(page);
  await page.goto("/incidents?status=active&priority=high&offset=25");
  await expect(page.getByLabel("Status filter")).toHaveValue("active");
  await expect(page.getByLabel("Priority filter")).toHaveValue("high");
  await expect(page).not.toHaveURL(/offset=25/);
  const searches: string[] = [];
  page.on("request", (request) => {
    if (
      request.url().includes("/api/incidents?") &&
      new URL(request.url()).searchParams.get("q")
    )
      searches.push(request.url());
  });
  await page
    .getByLabel("Search incidents")
    .pressSequentially("workflow-review");
  await expect(
    page.getByRole("link", { name: "Review workflow-review.env", exact: true }),
  ).toBeVisible();
  await expect.poll(() => searches.length).toBe(1);
  await page.reload();
  await expect(page.getByLabel("Search incidents")).toHaveValue(
    "workflow-review",
  );
  await page
    .getByRole("link", { name: "Review workflow-review.env", exact: true })
    .click();
  await expect(page).toHaveURL(new RegExp(`/incidents/${incident.id}`));
  await page
    .getByRole("link", { name: "← Incident queue", exact: true })
    .click();
  await expect(page.getByLabel("Search incidents")).toHaveValue(
    "workflow-review",
  );
  await expect(page.getByLabel("Priority filter")).toHaveValue("high");
  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(page.getByLabel("Status filter")).toHaveValue("");
  await page.goBack();
  await expect(page.getByLabel("Status filter")).toHaveValue("active");
  await expect(page.getByLabel("Search incidents")).toHaveValue(
    "workflow-review",
  );
  expect(errors).toEqual([]);
});

test("shared excerpts keep citation anchors and completed assessments stop polling", async ({
  page,
}) => {
  await page.clock.install();
  await signIn(page);
  const incident = await uploadCase(page);
  const detail = await (
    await page.request.get(`/api/incidents/${incident.id}`)
  ).json();
  await page.goto(`/incidents/${incident.id}`);
  await expect(page.locator(".evidence-reference")).toHaveCount(
    detail.evidence.length,
  );
  expect(await page.locator("article.evidence").count()).toBeLessThan(
    detail.evidence.length,
  );
  const requests: string[] = [];
  page.on("request", (request) => {
    if (/\/api\/investigations\/[^/?]+$/.test(request.url()))
      requests.push(request.url());
  });
  const loaded = page.waitForResponse(
    (response) =>
      /\/api\/investigations\/[^/?]+$/.test(response.url()) &&
      response.status() === 200,
  );
  await page.getByRole("button", { name: "Run offline assessment" }).click();
  await loaded;
  await expect(
    page.locator(".investigation-result .badge.completed"),
  ).toBeVisible();
  const links = await page.locator(".investigation-result .citations a").all();
  expect(links.length).toBeGreaterThan(0);
  for (const link of links) {
    const href = await link.getAttribute("href");
    await expect(page.locator(href!)).toHaveCount(1);
    const number =
      detail.evidence.findIndex(
        (item: { id: string }) => href === `#evidence-${item.id}`,
      ) + 1;
    await expect(link).toHaveText(`E${number} ↗`);
  }
  const count = requests.length;
  await page.clock.fastForward(13000);
  await expect(
    page.locator(".investigation-result .badge.completed"),
  ).toBeVisible();
  expect(requests.length).toBe(count);
  await page.screenshot({ path: "test-results/workflow-verification.png" });
});

test("slow queue responses are not cancelled by the polling interval", async ({
  page,
}) => {
  await page.clock.install();
  await signIn(page);
  const waiting: Route[] = [];
  await page.route("**/api/incidents?**", (route) => {
    waiting.push(route);
  });
  await page.goto("/incidents");
  await expect.poll(() => waiting.length).toBe(1);
  await page.clock.fastForward(6500);
  expect(waiting.length).toBe(1);
  await waiting[0].fulfill({
    json: { items: [], total: 0, offset: 0, limit: 25 },
  });
  await expect(
    page.getByRole("heading", { name: "No incidents in this view" }),
  ).toBeVisible();
});
