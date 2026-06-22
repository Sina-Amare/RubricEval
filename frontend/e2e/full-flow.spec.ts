import { expect, test } from "@playwright/test";

const TOKEN = process.env.OPERATOR_TOKEN || "e2e-token";
const ZIP = "e2e/fixtures/sample.zip";

test.beforeEach(async ({ page }) => {
  await page.addInitScript((t) => {
    window.localStorage.setItem("operator_token", t);
  }, TOKEN);
});

async function addCriterion(
  page: any,
  index: number,
  opts: { title: string; type: "scored" | "gate"; instructions: string },
) {
  await page.getByTestId("add-criterion").click();
  const row = page.getByTestId("criterion-row").nth(index);
  await row.locator('input[placeholder^="Criterion title"]').fill(opts.title);
  await row.locator("select").first().selectOption(opts.type);
  await row.locator("textarea").fill(opts.instructions);
}

test("create task -> publish -> submit zip -> live -> report with verified evidence", async ({
  page,
}) => {
  // Create a task.
  await page.goto("/");
  await page.getByTestId("new-task-name").fill("E2E Flow");
  await page.getByTestId("create-task").click();
  await expect(page).toHaveURL(/\/tasks\/.+\/edit/);
  const taskId = page.url().match(/tasks\/([^/]+)\/edit/)![1];

  // Build a rubric: one gate + two scored criteria.
  await addCriterion(page, 0, {
    title: "Has documentation",
    type: "gate",
    instructions: "Project includes `documentation`.",
  });
  await addCriterion(page, 1, {
    title: "Has tests",
    type: "scored",
    instructions: "Includes automated `test` functions.",
  });
  await addCriterion(page, 2, {
    title: "Implements add",
    type: "scored",
    instructions: "Implements an `add` function.",
  });

  // Publish.
  await page.getByTestId("publish").click();
  await expect(page.getByText(/Published v\d+ ·/)).toBeVisible(); // status w/ hash

  // Submit the fixture ZIP.
  await page.goto(`/tasks/${taskId}/submit`);
  await page.getByTestId("zip-input").setInputFiles(ZIP);
  await page.getByTestId("ingest").click();
  await expect(page.getByTestId("submission-summary")).toBeVisible();

  // Start the evaluation -> live view.
  await page.getByTestId("start-review").click();
  await expect(page).toHaveURL(/\/reviews\/.+\/live/);

  // Wait for completion, then open the report.
  await page.getByTestId("view-report").click({ timeout: 60_000 });
  await expect(page).toHaveURL(/\/reviews\/[^/]+$/);

  // Decision + verified evidence on real code.
  await expect(page.getByText("ACCEPT")).toBeVisible();
  const evidence = page.getByTestId("evidence-item").first();
  await expect(evidence).toBeVisible();
  await expect(page.getByText("test_add")).toBeVisible(); // real cited code
  await evidence.click();
});

test("theme toggle switches between light and dark", async ({ page }) => {
  await page.goto("/");
  const html = page.locator("html");
  const before = await html.evaluate((el) => el.classList.contains("dark"));
  await page.getByTestId("theme-toggle").click();
  await expect
    .poll(async () => html.evaluate((el: HTMLElement) => el.classList.contains("dark")))
    .toBe(!before);
  // persists across navigation
  await page.goto("/settings");
  expect(await html.evaluate((el: HTMLElement) => el.classList.contains("dark"))).toBe(!before);
});

test("settings shows the active model", async ({ page }) => {
  await page.goto("/settings");
  await expect(page.getByText("Active model")).toBeVisible();
  await expect(page.getByText(/via (litellm|fake)/)).toBeVisible();
});

test("dashboard shows the evaluate action on a task", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("new-task-name").fill("Discoverability");
  await page.getByTestId("create-task").click();
  await expect(page).toHaveURL(/\/tasks\/.+\/edit/);
  await page.goto("/");
  const card = page.getByTestId("task-card").first();
  await expect(card.getByText("Evaluate →")).toBeVisible();
});
