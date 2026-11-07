import { expect, test } from "@playwright/test";

test("institutional overview and report builder expose Department and Faculty reporting scopes", async ({ page, request }) => {
  const masters = await (await request.get("/api/masters")).json() as { departments: { id: number; is_active: boolean }[] };
  const department = masters.departments.find((item) => item.is_active);
  expect(department).toBeDefined();
  const facultyResponse = await request.post("/api/faculty", { data: {
    employee_id: "IRA-E2E-1", name: "Institutional Acceptance Faculty", department_id: department!.id,
    department_effective_from: "2025-07-01",
  } });
  expect(facultyResponse.ok(), await facultyResponse.text()).toBeTruthy();
  const faculty = await facultyResponse.json() as { id: number; name: string };
  const publicationResponse = await request.post("/api/publications", { data: {
    doi: "10.1234/institutional-acceptance", title: "Institutional Acceptance Publication", publication_type: "JOURNAL",
    publication_date: "2026-09-18", journal_conference_name: "VCE Journal", indexing: [],
    authors: [{ author_order: 1, author_name_from_source: faculty.name, person_type: "FACULTY", faculty_id: faculty.id, is_internal: true, is_claiming_faculty: true }],
  } });
  expect(publicationResponse.ok(), await publicationResponse.text()).toBeTruthy();

  await page.goto("/?from_date=2026-07-01&to_date=2026-12-31");
  const scope = page.getByRole("combobox", { name: "Scope", exact: true });
  await scope.selectOption("DEPARTMENT");
  const overviewDepartment = page.getByRole("combobox", { name: "Department", exact: true });
  await overviewDepartment.selectOption(String(department!.id));
  await expect(page.getByRole("combobox", { name: "Attribution", exact: true })).toHaveValue("CURRENT");
  await page.getByRole("combobox", { name: "Attribution", exact: true }).selectOption("AT_ACTIVITY_DATE");
  await expect(page.getByText(/Attribution data quality/i)).toBeVisible();

  await scope.selectOption("FACULTY");
  await page.getByRole("combobox", { name: "Faculty", exact: true }).selectOption(String(faculty.id));
  await expect(page.getByText(/Open the selected Faculty/i)).toBeVisible();

  await page.goto("/publications/reports");
  const reportScope = page.getByRole("combobox", { name: "Reporting Scope", exact: true });
  await expect(reportScope).toHaveValue("INSTITUTION");
  await reportScope.selectOption("DEPARTMENT");
  await page.getByRole("combobox", { name: "Department", exact: true }).selectOption(String(department!.id));
  await page.getByRole("button", { name: "Generate Preview", exact: true }).click();
  await expect(page.getByRole("heading", { name: /Preview ·/ })).toBeVisible();
  await reportScope.selectOption("FACULTY");
  await page.getByRole("combobox", { name: "Faculty", exact: true }).selectOption(String(faculty.id));
  await page.getByRole("combobox", { name: "Faculty Relationship", exact: true }).selectOption("CONTRIBUTING");
  await page.getByRole("button", { name: "Generate Preview", exact: true }).click();
  await expect(page.getByRole("heading", { name: /Preview ·/ })).toBeVisible();
});
