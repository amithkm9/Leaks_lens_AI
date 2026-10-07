import { expect, test, type Locator } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import type {
  Detail,
  Job,
  Organization,
  RemediationTask,
  Source,
} from "../src/types";

// Runs only with playwright.docs.config.ts, which starts a disposable database.
// All content is synthetic; the real workspace is never opened or seeded.
test("capture the README product tour", async ({ page }) => {
  const output = resolve(import.meta.dirname, "../../docs/images");
  await mkdir(output, { recursive: true });
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
  const auth = await (await page.request.get("/api/auth/me")).json();
  const headers = { "X-CSRF-Token": auth.csrf_token };
  async function post<T>(path: string, data: unknown): Promise<T> {
    const response = await page.request.post(`/api${path}`, { headers, data });
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.json();
  }
  async function scanFinished(id: string) {
    await expect
      .poll(
        async () =>
          (await (await page.request.get(`/api/scans/${id}`)).json()).status,
      )
      .toBe("completed");
  }
  async function screenshot(name: string, locator?: Locator) {
    await expect(page.getByRole("alert")).toHaveCount(0);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBeTruthy();
    const options = {
      path: resolve(output, `${name}.png`),
      animations: "disabled" as const,
    };
    if (locator) await locator.screenshot(options);
    else await page.screenshot(options);
  }
  const sources: Source[] = (
    await (await page.request.get("/api/sources")).json()
  ).items;
  for (const source of sources) {
    await post(`/sources/${source.id}/archive`, {
      expected_revision: source.revision,
      archived: true,
    });
  }
  const organization = await post<Organization>("/organizations", {
    name: "Northstar Labs",
    aliases: ["Northstar"],
    domains: ["northstar-labs.test"],
    reference_ids: ["NS-DEMO-042"],
    importance: "normal",
  });
  await post("/organizations", {
    name: "Cedar Analytics",
    aliases: ["Cedar"],
    domains: ["cedar-analytics.test"],
    reference_ids: [],
    importance: "normal",
  });
  const inputs = [
    {
      name: "northstar-service.env",
      content:
        "# SYNTHETIC DOCUMENTATION FIXTURE\n# Northstar Labs · reference NS-DEMO-042\nSERVICE_HOST=api.northstar-labs.test\napi_key=synthetic-northstar-documentation-credential-123456\n# Follow-up: rotate the fixture credential and verify revocation.\n",
    },
    {
      name: "cedar-customer-export.csv",
      content:
        "company,email,reference\nCedar Analytics,alice@cedar-analytics.test,SYNTHETIC-001\nCedar Analytics,bob@cedar-analytics.test,SYNTHETIC-002\n",
    },
    {
      name: "northstar-integration.json",
      content: JSON.stringify(
        {
          synthetic: true,
          organization: "Northstar Labs",
          reference: "NS-DEMO-042",
          contact: "integration@northstar-labs.test",
          api_key: "synthetic-integration-documentation-credential-456789",
        },
        null,
        2,
      ),
    },
  ];
  const cases: { detail: Detail; job: Job }[] = [];
  for (const input of inputs) {
    const uploaded = await page.request.post("/api/uploads", {
      headers,
      multipart: {
        file: {
          name: input.name,
          mimeType: "text/plain",
          buffer: Buffer.from(input.content),
        },
      },
    });
    expect(uploaded.status()).toBe(202);
    const job: Job = await uploaded.json();
    await scanFinished(job.id);
    const incident = (
      await (
        await page.request.get(
          `/api/incidents?q=${encodeURIComponent(input.name)}`,
        )
      ).json()
    ).items[0];
    const detail: Detail = await (
      await page.request.get(`/api/incidents/${incident.id}`)
    ).json();
    expect(detail.evidence.length).toBeGreaterThan(0);
    expect(JSON.stringify(detail)).not.toContain(
      "synthetic-northstar-documentation-credential-123456",
    );
    cases.push({ detail, job });
  }
  const member = (
    await (await page.request.get("/api/workspace/members")).json()
  ).items[0];
  const day = (offset: number) =>
    new Date(Date.now() + offset * 86400000).toISOString().slice(0, 10);
  async function task(index: number, title: string, deadline: number) {
    const incident = cases[index].detail;
    return post<RemediationTask>(
      `/incidents/${incident.id}/remediation-tasks`,
      {
        title,
        analysis_revision: 1,
        owner_id: member.id,
        due_date: day(deadline),
        evidence_ids: [incident.evidence[0].id],
      },
    );
  }
  const rotate = await task(0, "Rotate the Northstar service credential", -1);
  await task(1, "Review access to the Cedar customer export", 1);
  const integration = await task(
    2,
    "Remove the integration credential from shared files",
    2,
  );
  async function update(
    task: RemediationTask,
    values: Record<string, unknown>,
  ) {
    const response = await page.request.put(
      `/api/remediation-tasks/${task.id}`,
      {
        headers,
        data: {
          title: task.title,
          analysis_revision: task.analysis_revision,
          owner_id: task.owner_id,
          due_date: task.due_date,
          evidence_ids: task.evidence_ids,
          expected_revision: task.revision,
          status: "in_progress",
          reason: "Assigned follow-up for the synthetic documentation case.",
          ...values,
        },
      },
    );
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.json() as Promise<RemediationTask>;
  }
  const progress = await update(rotate, {
    action_taken:
      "Identified the service owner; replacement credential is being prepared.",
  });
  await update(integration, {
    status: "completed",
    action_taken:
      "Removed the synthetic credential from the shared integration file.",
    reason: "Action recorded; independent verification is still pending.",
  });
  const first = cases[0].detail;
  await post(`/incidents/${first.id}/reviews`, {
    analysis_revision: 1,
    action: "confirm",
    reason:
      "Confirmed the synthetic credential pattern and Northstar reference. This upload does not establish public exposure.",
  });
  const investigation = await post<{ id: string }>(
    `/incidents/${first.id}/investigations`,
    { analysis_revision: 1, mode: "offline" },
  );
  await expect
    .poll(
      async () =>
        (
          await (
            await page.request.get(`/api/investigations/${investigation.id}`)
          ).json()
        ).status,
    )
    .toBe("completed");

  await page.goto("/");
  await expect(
    page.getByRole("region", { name: "Remediation follow-up" }),
  ).toContainText("Rotate the Northstar");
  await expect(
    page.getByRole("link", { name: "1 Awaiting verification", exact: true }),
  ).toBeVisible();
  await screenshot("overview");
  await page.goto("/sources");
  await expect(
    page.getByRole("button", { name: "Configure source", exact: true }),
  ).toBeInViewport({ ratio: 1 });
  await expect(
    page.getByRole("region", { name: "Connected sources" }),
  ).toContainText("northstar-service.env");
  await expect(
    page.getByRole("region", { name: "Scan activity" }),
  ).toContainText("completed");
  await screenshot("sources");
  await page.goto("/incidents");
  await expect(
    page.getByRole("link", {
      name: "Review northstar-service.env",
      exact: true,
    }),
  ).toBeVisible();
  await screenshot("incident-queue");
  await page.goto(`/incidents/${first.id}`);
  await expect(
    page.getByRole("heading", { name: "Redacted evidence" }),
  ).toBeVisible();
  await expect(
    page.locator(".investigation-result .badge.completed"),
  ).toBeVisible();
  await screenshot("incident-review");
  await page.goto("/remediation?state=all");
  await expect(
    page.getByRole("link", { name: rotate.title, exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Awaiting verification", { exact: true }),
  ).toBeVisible();
  await screenshot("remediation");

  await update(progress, {
    status: "completed",
    action_taken:
      "Rotated the synthetic service credential and updated the test integration.",
    verification_method: "credential_rotation",
    verification_notes:
      "The synthetic service owner confirmed the old credential is revoked. Other source copies remain a separate check.",
    reason: "Recorded the revocation check after the rotation was completed.",
  });
  await page.goto(`/incidents/${first.id}#remediation`);
  const taskPanel = page.getByRole("region", {
    name: "Remediation tasks",
    exact: true,
  });
  await expect(
    taskPanel.getByText("Analyst verified", { exact: false }),
  ).toBeVisible();
  await screenshot("remediation-verification", taskPanel);

  const refreshed = await page.request.put(
    `/api/organizations/${organization.id}`,
    {
      headers,
      data: {
        name: organization.name,
        aliases: organization.aliases,
        domains: organization.domains,
        reference_ids: organization.reference_ids,
        importance: "critical",
      },
    },
  );
  expect(refreshed.ok()).toBeTruthy();
  const reanalysis = await post<Job>(`/incidents/${first.id}/reanalyses`, {
    source_id: cases[0].job.source_id,
    expected_analysis_revision: 1,
    reason:
      "Reassess priority after the authorized organization profile was updated.",
  });
  await scanFinished(reanalysis.id);
  await page.goto(`/incidents/${first.id}`);
  await expect(
    page.getByRole("heading", { name: "Analysis revision 2", exact: true }),
  ).toBeVisible();
  await page.getByText("Compare analyses", { exact: true }).click();
  const comparison = page.getByRole("region", {
    name: "Compare analyses",
    exact: true,
  });
  await expect(
    comparison.getByText("Redacted text is unchanged.", { exact: true }),
  ).toBeVisible();
  await screenshot("analysis-comparison", comparison);
  expect(errors).toEqual([]);
});
