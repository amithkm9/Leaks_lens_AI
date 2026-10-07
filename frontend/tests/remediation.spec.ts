import { expect, test } from "@playwright/test";

test("remediation ownership → overdue queue → action → verification → history", async ({
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
  await page.getByLabel("Upload document", { exact: true }).setInputFiles({
    name: "remediation-fixture.env",
    mimeType: "text/plain",
    buffer: Buffer.from(
      "SYNTHETIC TASK TEST\napi_key=synthetic-task-browser-secret-123456\n",
    ),
  });
  await expect(page.getByRole("status")).toContainText("Upload accepted");
  await page.getByRole("link", { name: "Incidents", exact: true }).click();
  await page
    .getByRole("link", { name: "Review remediation-fixture.env", exact: true })
    .click();
  const incidentUrl = page.url();
  const tasks = page.getByRole("region", {
    name: "Remediation tasks",
    exact: true,
  });
  await tasks.getByRole("button", { name: "Add task", exact: true }).click();
  let dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Task title", { exact: true })
    .fill("Rotate fixture credential");
  await dialog
    .getByLabel("Task owner", { exact: true })
    .selectOption({ label: "browser@example.test" });
  await dialog.getByLabel("Due date (UTC)", { exact: true }).fill("2000-01-01");
  await dialog.getByRole("checkbox").first().check();
  await dialog
    .getByRole("button", { name: "Create task", exact: true })
    .click();
  await expect(tasks.getByRole("status")).toContainText(
    "Remediation task created",
  );
  await expect(tasks.getByText("overdue", { exact: true })).toBeVisible();
  await expect(
    tasks.getByRole("link", { name: "Evidence 1 ↗", exact: true }),
  ).toBeVisible();

  await page.getByRole("link", { name: "Overview", exact: true }).click();
  const followUp = page.getByRole("region", {
    name: "Remediation follow-up",
    exact: true,
  });
  await expect(followUp).toContainText("Rotate fixture credential");
  await followUp
    .getByRole("link", { name: "1 Overdue tasks", exact: true })
    .click();
  await expect(page).toHaveURL(/remediation\?state=overdue/);
  await page.getByLabel("Assigned to", { exact: true }).selectOption("me");
  await page.reload();
  await expect(page.getByLabel("Task view", { exact: true })).toHaveValue(
    "overdue",
  );
  await expect(page.getByLabel("Assigned to", { exact: true })).toHaveValue(
    "me",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("link", { name: "Rotate fixture credential", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "test-results/remediation-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: "test-results/remediation-queue.png",
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "Rotate fixture credential", exact: true })
    .click();
  await tasks.getByRole("button", { name: "Update task", exact: true }).click();
  dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Task status", { exact: true })
    .selectOption("completed");
  await dialog
    .getByLabel("Action taken", { exact: true })
    .fill("Rotated the synthetic credential in the test service.");
  await dialog
    .getByLabel("Reason for change", { exact: true })
    .fill("Action complete; verify revocation next.");
  await dialog
    .getByRole("button", { name: "Save task changes", exact: true })
    .click();
  await expect(
    tasks.getByText("Awaiting verification", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".summary-panel .badge.open")).toBeVisible();

  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await followUp
    .getByRole("link", { name: "1 Awaiting verification", exact: true })
    .click();
  await expect(page).toHaveURL(/state=awaiting_verification/);
  await page
    .getByRole("link", { name: "Rotate fixture credential", exact: true })
    .click();
  await tasks.getByRole("button", { name: "Update task", exact: true }).click();
  dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Verification method", { exact: true })
    .selectOption("credential_rotation");
  await dialog
    .getByLabel("Verification notes", { exact: true })
    .fill("The synthetic service confirms the previous credential is revoked.");
  await dialog
    .getByLabel("Reason for change", { exact: true })
    .fill("Checked revocation after rotation.");
  await dialog
    .getByRole("button", { name: "Save task changes", exact: true })
    .click();
  await expect(
    tasks.getByText("Analyst verified", { exact: false }),
  ).toBeVisible();
  await tasks
    .getByRole("button", { name: "Task history", exact: true })
    .click();
  dialog = page.getByRole("dialog");
  await expect(
    dialog.getByText("Revision 3 · completed", { exact: true }),
  ).toBeVisible();
  await expect(dialog.getByText("Task created", { exact: true })).toBeVisible();
  await dialog
    .getByText("Task state at this change", { exact: true })
    .first()
    .click();
  await expect(
    dialog.getByText(
      "The synthetic service confirms the previous credential is revoked.",
      { exact: true },
    ),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Close", exact: true }).click();
  await page.screenshot({
    path: "test-results/remediation-incident.png",
    fullPage: true,
  });

  const exported = await page.request.get(
    `${incidentUrl.replace("/incidents/", "/api/incidents/")}/export`,
  );
  const report = (await exported.json()).report;
  expect(report.status).toBe("open");
  expect(report.remediation.items[0].verified_at).toBeTruthy();
  expect(report.remediation.items[0].evidence_ids).toHaveLength(1);
  expect(JSON.stringify(report)).not.toContain(
    "synthetic-task-browser-secret-123456",
  );
  expect(errors).toEqual([]);
});
