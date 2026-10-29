import { expect, test } from "@playwright/test";

const period = "from_date=2026-07-01&to_date=2026-12-31";

test("FDP and certification KPI selections do not refetch or replace their summaries", async ({ page, request }) => {
  const create = async (path: string, data: object) => {
    const response = await request.post(`/api${path}`, { data });
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.json();
  };

  // Playwright starts against an isolated, intentionally empty database. Build
  // the Faculty Master fixtures here and retain their returned stable IDs.
  const facultyA = await create("/faculty", { employee_id: "KPI-E2E-A", name: "KPI Faculty A" });
  const facultyB = await create("/faculty", { employee_id: "KPI-E2E-B", name: "KPI Faculty B" });

  await create("/fdp-activities", {
    title: "KPI FDP", activity_type: "FDP", organizing_institution: "Vardhaman",
    start_date: "2026-08-01", duration_value: 1, duration_unit: "DAYS",
    participants: [{ faculty_id: facultyA.id, role: "ATTENDEE" }], speakers: [],
  });
  await create("/fdp-activities", {
    title: "KPI STTP", activity_type: "STTP", organizing_institution: "Vardhaman",
    start_date: "2026-08-02", duration_value: 1, duration_unit: "DAYS",
    participants: [{ faculty_id: facultyB.id, role: "ATTENDEE" }], speakers: [],
  });
  await create("/certifications", {
    faculty_id: facultyA.id, name: "KPI completed", category: "MOOC", provider: "Provider",
    status: "COMPLETED", completion_date: "2026-08-01",
  });
  await create("/certifications", {
    faculty_id: facultyB.id, name: "KPI current", category: "OTHER", provider: "Provider", status: "IN_PROGRESS",
  });

  await page.goto(`/fdp?${period}`);
  const fdpCards = [
    ["Distinct Activities: 2", "FDPs: 1", "STTPs: 1", "Workshops: 0"],
  ];
  for (const names of fdpCards) for (const name of names) await expect(page.getByRole("button", { name, exact: true })).toBeVisible();

  let fdpSummaryRequests = 0;
  page.on("request", (request) => {
    if (request.url().includes("/api/fdp-dashboard?")) fdpSummaryRequests += 1;
  });
  await page.getByRole("button", { name: "Workshops: 0", exact: true }).click();
  await expect(page.locator("#fdp-records")).toContainText("No activities match the current filters.");
  await page.getByRole("button", { name: "FDPs: 1", exact: true }).click();
  await expect(page.locator("#fdp-records")).toContainText("KPI FDP");
  for (const name of fdpCards[0]) await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
  expect(fdpSummaryRequests).toBe(0);
  await page.getByRole("button", { name: "Clear KPI selection", exact: true }).click();
  await expect(page.locator("#fdp-records")).toContainText("KPI STTP");
  for (const name of fdpCards[0]) await expect(page.getByRole("button", { name, exact: true })).toBeVisible();

  await page.goto(`/certifications?${period}`);
  const certificationCards = ["Certifications completed in period: 1", "Completed: 1", "In progress: 1", "MOOCs: 1"];
  for (const name of certificationCards) await expect(page.getByRole("button", { name, exact: true })).toBeVisible();

  let certificationSummaryRequests = 0;
  page.on("request", (request) => {
    if (request.url().includes("/api/certification-dashboard?")) certificationSummaryRequests += 1;
  });
  await page.getByRole("button", { name: "NPTEL / SWAYAM: 0", exact: true }).click();
  await expect(page.locator("#certification-records")).toContainText("No certifications match the current filters.");
  await page.getByRole("button", { name: "In progress: 1", exact: true }).click();
  await expect(page.locator("#certification-records")).toContainText("KPI current");
  for (const name of certificationCards) await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
  expect(certificationSummaryRequests).toBe(0);
  await page.getByRole("button", { name: "Clear KPI selection", exact: true }).click();
  await expect(page.locator("#certification-records")).toContainText("KPI completed");
  for (const name of certificationCards) await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
});
