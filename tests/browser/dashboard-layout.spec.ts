import { expect, test } from "@playwright/test";

let departmentFixturePublicationId: number | undefined;

test.afterEach(async ({ request }) => {
  if (departmentFixturePublicationId === undefined) return;
  const response = await request.delete(`/api/publications/${departmentFixturePublicationId}/permanent`);
  departmentFixturePublicationId = undefined;
  expect(response.ok()).toBeTruthy();
});

test("institutional reporting controls and publication subtype filters stay compact and applicable", async ({ page, request }) => {
  const mastersResponse = await request.get("/api/masters");
  expect(mastersResponse.ok()).toBeTruthy();
  const masters = await mastersResponse.json() as { departments: { id: number; is_active: boolean }[] };
  const fixtureDepartment = masters.departments.find((department) => department.is_active);
  expect(fixtureDepartment).toBeDefined();

  const facultyResponse = await request.post("/api/faculty", {
    data: {
      employee_id: "E2E-DEPT-PUB",
      name: "Department Filter Faculty",
      department_id: fixtureDepartment!.id,
      department_effective_from: "2026-07-01",
    },
  });
  expect(facultyResponse.ok()).toBeTruthy();
  const faculty = await facultyResponse.json() as { id: number; name: string };
  const publicationResponse = await request.post("/api/publications", {
    data: {
      title: "Department Filter Publication",
      publication_type: "JOURNAL",
      publication_date: "2026-09-18",
      indexing: [],
      authors: [{
        author_order: 1,
        author_name_from_source: faculty.name,
        person_type: "FACULTY",
        faculty_id: faculty.id,
        student_id: null,
        is_internal: true,
        is_claiming_faculty: true,
        is_first_author: true,
        is_corresponding_author: false,
        affiliation_from_source: [],
        matching_status: "EXACT",
      }],
    },
  });
  expect(publicationResponse.ok()).toBeTruthy();
  departmentFixturePublicationId = (await publicationResponse.json() as { id: number }).id;

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Research Overview", exact: true })).toBeVisible();
  await expect(page.getByText("Institutional research performance and activity", { exact: true })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Reporting Period", exact: true })).toBeVisible();
  await expect(page.getByLabel("From Date", { exact: true })).toHaveCount(0);
  await page.getByRole("combobox", { name: "Scope", exact: true }).selectOption("DEPARTMENT");
  await expect(page.getByRole("combobox", { name: "Department", exact: true })).toBeVisible();

  await page.goto("/publications");
  const department = page.getByRole("combobox", { name: "Department", exact: true });
  await expect(department).toBeVisible();
  // Native select options are not visible while the control is closed. Check
  // the default value and option content rather than its rendered visibility.
  await expect(department).toHaveValue("");
  await expect(department.locator('option[value=""]')).toHaveText("All Departments");

  // The isolated browser fixture supplies an active Department. Selecting it
  // must scope the dashboard request and expose its attribution control.
  const selectedDepartmentId = String(fixtureDepartment!.id);
  await expect(department.locator(`option[value="${selectedDepartmentId}"]`)).toHaveCount(1);
  await Promise.all([
    page.waitForResponse((response) => {
      const url = new URL(response.url());
      return url.pathname.endsWith("/publication-dashboard") && url.searchParams.get("department_id") === selectedDepartmentId;
    }),
    department.selectOption(selectedDepartmentId),
  ]);
  await expect(department).toHaveValue(selectedDepartmentId);
  await expect(page.getByRole("combobox", { name: "Department Attribution", exact: true })).toBeVisible();
  await page.getByRole("button", { name: /^Total Publications: \d+$/ }).click();
  await expect(page.locator("#papers").getByRole("link", { name: "Department Filter Publication", exact: true })).toBeVisible();
  const publicationType = page.getByRole("combobox", { name: "Publication Type", exact: true });
  await expect(page.getByRole("combobox", { name: "Conference Scope", exact: true })).toHaveCount(0);
  await expect(page.getByRole("combobox", { name: "Quartile", exact: true })).toHaveCount(0);
  await publicationType.selectOption("JOURNAL");
  await expect(page.getByRole("combobox", { name: "Quartile", exact: true })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Conference Scope", exact: true })).toHaveCount(0);
  await publicationType.selectOption("CONFERENCE");
  await expect(page.getByRole("combobox", { name: "Conference Scope", exact: true })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Quartile", exact: true })).toHaveCount(0);
});

test("patent and book dashboards provide Department scope controls", async ({ page, request }) => {
  const mastersResponse = await request.get("/api/masters");
  expect(mastersResponse.ok()).toBeTruthy();
  const masters = await mastersResponse.json() as { departments: { id: number; is_active: boolean }[] };
  const department = masters.departments.find((item) => item.is_active);
  expect(department).toBeDefined();
  const departmentId = String(department!.id);

  for (const module of [
    { path: "/patents", dashboard: "/patent-dashboard" },
    { path: "/books", dashboard: "/book-dashboard" },
  ]) {
    await page.goto(module.path);
    const selector = page.getByRole("combobox", { name: "Department", exact: true });
    await expect(selector).toHaveValue("");
    await expect(selector.locator('option[value=""]')).toHaveText("All Departments");
    await expect(selector.locator(`option[value="${departmentId}"]`)).toHaveCount(1);
    await Promise.all([
      page.waitForResponse((response) => {
        const url = new URL(response.url());
        return url.pathname.endsWith(module.dashboard) && url.searchParams.get("department_id") === departmentId;
      }),
      selector.selectOption(departmentId),
    ]);
    await expect(page.getByRole("combobox", { name: "Department Attribution", exact: true })).toBeVisible();
    await page.getByRole("combobox", { name: "Department Attribution", exact: true }).selectOption("AT_ACTIVITY_DATE");
    await expect(page.getByText(/verified primary Department affiliations/i)).toBeVisible();
  }
});

test("FDP and certification dashboards provide Department scope controls", async ({ page, request }) => {
  const mastersResponse = await request.get("/api/masters");
  expect(mastersResponse.ok()).toBeTruthy();
  const masters = await mastersResponse.json() as { departments: { id: number; is_active: boolean }[] };
  const department = masters.departments.find((item) => item.is_active);
  expect(department).toBeDefined();
  const departmentId = String(department!.id);

  for (const module of [
    { path: "/fdp", dashboard: "/fdp-dashboard", historicalMessage: /activity start date/i },
    { path: "/certifications", dashboard: "/certification-dashboard", historicalMessage: /completion date/i },
  ]) {
    await page.goto(module.path);
    const selector = page.getByRole("combobox", { name: "Department", exact: true });
    await expect(selector).toHaveValue("");
    await expect(selector.locator('option[value=""]')).toHaveText("All Departments");
    await Promise.all([
      page.waitForResponse((response) => {
        const url = new URL(response.url());
        return url.pathname.endsWith(module.dashboard) && url.searchParams.get("department_id") === departmentId;
      }),
      selector.selectOption(departmentId),
    ]);
    await expect(page.getByRole("combobox", { name: "Department Attribution", exact: true })).toBeVisible();
    await page.getByRole("combobox", { name: "Department Attribution", exact: true }).selectOption("AT_ACTIVITY_DATE");
    await expect(page.locator("p.compact-note", { hasText: module.historicalMessage })).toBeVisible();
  }
});

test("funding dashboards provide Department attribution controls for every category", async ({ page, request }) => {
  const mastersResponse = await request.get("/api/masters");
  expect(mastersResponse.ok()).toBeTruthy();
  const masters = await mastersResponse.json() as { departments: { id: number; is_active: boolean }[] };
  const department = masters.departments.find((item) => item.is_active);
  expect(department).toBeDefined();
  const departmentId = String(department!.id);

  for (const module of [
    { path: "/research-projects", category: "SPONSORED_RESEARCH" },
    { path: "/consultancy", category: "CONSULTANCY" },
    { path: "/seed-money", category: "INTERNAL_GRANT" },
  ]) {
    await page.goto(module.path);
    const selector = page.getByRole("combobox", { name: "Department", exact: true });
    await expect(selector).toHaveValue("");
    await expect(selector.locator('option[value=""]')).toHaveText("All Departments");
    await expect(selector.locator(`option[value="${departmentId}"]`)).toHaveCount(1);
    await Promise.all([
      page.waitForResponse((response) => {
        const url = new URL(response.url());
        return url.pathname.endsWith("/funding-dashboard")
          && url.searchParams.get("category") === module.category
          && url.searchParams.get("department_id") === departmentId;
      }),
      selector.selectOption(departmentId),
    ]);
    const attribution = page.getByRole("combobox", { name: "Department Attribution", exact: true });
    await expect(attribution).toHaveValue("CURRENT");
    await attribution.selectOption("AT_ACTIVITY_DATE");
    await expect(page.locator("p.compact-note", { hasText: /sanction date/i })).toBeVisible();
    await page.getByRole("button", { name: "Reset filters", exact: true }).click();
    await expect(selector).toHaveValue("");
    await expect(attribution).toHaveCount(0);
  }
});

