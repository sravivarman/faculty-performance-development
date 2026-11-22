import { expect, test } from "@playwright/test";

let departmentFixturePublicationId: number | undefined;

async function expectFiltersBeforeKpis(page: import("@playwright/test").Page, kpiName: RegExp) {
  const panel = page.locator('section[aria-label="Overview filters"]');
  const kpi = page.getByRole("button", { name: kpiName });
  await expect(panel).toHaveCount(1);
  await expect(panel).toBeVisible();
  await expect(kpi).toBeVisible();
  const [filterBox, kpiBox] = await Promise.all([panel.boundingBox(), kpi.boundingBox()]);
  if (!filterBox || !kpiBox) throw new Error("Expected visible filter heading and KPI card");
  expect(filterBox.y).toBeLessThan(kpiBox.y);
}

async function expectUnifiedFilterPanel(page: import("@playwright/test").Page) {
  const panel = page.locator('section[aria-label="Overview filters"]');
  const grid = panel.locator(".overview-filter-grid");
  await expect(panel).toHaveCount(1);
  await expect(grid.getByRole("combobox", { name: "Reporting Period", exact: true })).toBeVisible();
  await expect(panel.locator(".reporting-period")).toHaveCount(0);
  await expect(panel.locator(".overview-filter-controls")).toHaveCount(0);
  await expect(grid.locator(".overview-range-summary")).toHaveCount(0);
  await expect(panel.locator(".overview-filter-footer .overview-range-summary")).toBeVisible();
  await expect(panel.getByRole("button", { name: "Reset Filters", exact: true })).toHaveCount(1);
  if (await page.evaluate(() => window.innerWidth > 720)) {
    const [periodBox, departmentBox] = await Promise.all([
      grid.getByRole("combobox", { name: "Reporting Period", exact: true }).boundingBox(),
      grid.getByRole("combobox", { name: "Department", exact: true }).boundingBox(),
    ]);
    if (!periodBox || !departmentBox) throw new Error("Expected aligned first-row filters");
    expect(Math.abs(periodBox.y - departmentBox.y)).toBeLessThanOrEqual(1);
  }
}

async function expectMobileFilterLayout(page: import("@playwright/test").Page, path: string, kpiName: RegExp) {
  await page.goto(path);
  await expectUnifiedFilterPanel(page);
  await expectFiltersBeforeKpis(page, kpiName);
  expect(await page.locator(".overview-filter-grid").evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/).length)).toBe(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
}

test.afterEach(async ({ request }) => {
  if (departmentFixturePublicationId === undefined) return;
  const response = await request.delete(`/api/publications/${departmentFixturePublicationId}/permanent`);
  departmentFixturePublicationId = undefined;
  expect(response.ok()).toBeTruthy();
});

test("institutional reporting controls and publication subtype filters stay compact and applicable", async ({ page, request }) => {
  await page.setViewportSize({ width: 1366, height: 900 });
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
  await expectUnifiedFilterPanel(page);
  await expectFiltersBeforeKpis(page, /^Total Publications:/);
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
  const studentParticipation = page.getByRole("combobox", { name: "Student Participation", exact: true });
  await expect(studentParticipation).toHaveValue("");
  await expect(studentParticipation.locator('option[value=""]')).toHaveText("All Publications");
  await Promise.all([
    page.waitForResponse((response) => new URL(response.url()).pathname.endsWith("/publication-dashboard") && new URL(response.url()).searchParams.get("student_participation") === "true"),
    studentParticipation.selectOption("true"),
  ]);
  await expect(studentParticipation).toHaveValue("true");
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
    await expectUnifiedFilterPanel(page);
    await expectFiltersBeforeKpis(page, /^Unique Patents:|^Total Works:/);
    if (module.path === "/books") {
      await expect(page.getByRole("combobox", { name: "Cross-Department Collaboration", exact: true })).toHaveCount(0);
      await expect(page.getByRole("combobox", { name: "External Collaboration", exact: true })).toHaveCount(0);
      const workType = page.getByRole("combobox", { name: "Work Type", exact: true });
      await expect(workType).toHaveValue("");
      await Promise.all([
        page.waitForResponse((response) => {
          const url = new URL(response.url());
          return url.pathname.endsWith("/book-dashboard") && url.searchParams.get("work_type") === "BOOK";
        }),
        workType.selectOption("BOOK"),
      ]);
      await expect(workType).toHaveValue("BOOK");
    }
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
    if (module.path === "/books") {
      await page.getByRole("button", { name: "Reset Filters", exact: true }).click();
      await expect(page.getByRole("combobox", { name: "Work Type", exact: true })).toHaveValue("");
      await expect(selector).toHaveValue("");
      await expect(page.getByRole("combobox", { name: "Reporting Period", exact: true })).toHaveValue("This Academic Year");

      const dashboardRequest = page.waitForRequest((request) => {
        const url = new URL(request.url());
        return url.pathname.endsWith("/book-dashboard")
          && !url.searchParams.has("interdepartmental")
          && !url.searchParams.has("external_collaboration");
      });
      await page.goto("/books?interdepartmental=true&external_collaboration=false");
      await dashboardRequest;
      await expect(page.getByRole("combobox", { name: "Cross-Department Collaboration", exact: true })).toHaveCount(0);
      await expect(page.getByRole("combobox", { name: "External Collaboration", exact: true })).toHaveCount(0);
    }
  }
});

test("custom dates use a popover without moving the Patent primary filter grid", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 900 });
  await page.goto("/patents");
  await expectUnifiedFilterPanel(page);
  const grid = page.locator(".overview-filter-grid");
  const reportingPeriod = grid.getByRole("combobox", { name: "Reporting Period", exact: true });
  const department = grid.getByRole("combobox", { name: "Department", exact: true });
  const patentType = grid.getByRole("combobox", { name: "Patent Type", exact: true });
  const patentStatus = grid.getByRole("combobox", { name: "Patent Status", exact: true });
  const original = await Promise.all([reportingPeriod.boundingBox(), department.boundingBox(), patentType.boundingBox(), patentStatus.boundingBox()]);
  if (original.some((box) => !box)) throw new Error("Expected all first-row Patent filters");
  const [periodBox, departmentBox, typeBox, statusBox] = original as NonNullable<typeof original[number]>[];
  expect(periodBox.x).toBeLessThan(departmentBox.x);
  expect(departmentBox.x).toBeLessThan(typeBox.x);
  expect(typeBox.x).toBeLessThan(statusBox.x);
  expect(Math.abs(periodBox.y - departmentBox.y)).toBeLessThanOrEqual(1);
  expect(Math.abs(periodBox.y - typeBox.y)).toBeLessThanOrEqual(1);
  expect(Math.abs(periodBox.y - statusBox.y)).toBeLessThanOrEqual(1);

  await reportingPeriod.selectOption("Custom");
  const setDates = page.getByRole("button", { name: "Set dates", exact: true });
  await expect(setDates).toBeVisible();
  await expect(page.getByRole("dialog", { name: "Custom date range", exact: true })).toHaveCount(0);
  const afterPresetChange = await Promise.all([department.boundingBox(), patentType.boundingBox(), patentStatus.boundingBox()]);
  for (const [before, after] of [[departmentBox, afterPresetChange[0]], [typeBox, afterPresetChange[1]], [statusBox, afterPresetChange[2]]] as const) {
    if (!after) throw new Error("Expected stable Patent filter positions");
    expect(Math.abs(before.x - after.x)).toBeLessThanOrEqual(1);
    expect(Math.abs(before.y - after.y)).toBeLessThanOrEqual(1);
  }

  await setDates.click();
  const dialog = page.getByRole("dialog", { name: "Custom date range", exact: true });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("From Date", { exact: true }).fill("2026-08-01");
  await dialog.getByLabel("To Date", { exact: true }).fill("2026-08-31");
  const dashboardResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname.endsWith("/patent-dashboard") && url.searchParams.get("from_date") === "2026-08-01" && url.searchParams.get("to_date") === "2026-08-31";
  });
  await dialog.getByRole("button", { name: "Apply range", exact: true }).click();
  await dashboardResponse;
  await expect(dialog).toHaveCount(0);
  await expect(page.locator(".overview-range-summary")).toContainText("Custom Range · 01-08-2026 to 31-08-2026");
  await page.getByRole("button", { name: "Reset Filters", exact: true }).click();
  await expect(reportingPeriod).toHaveValue("This Academic Year");
});

test("FDP and certification dashboards provide Department scope controls", async ({ page, request }) => {
  const mastersResponse = await request.get("/api/masters");
  expect(mastersResponse.ok()).toBeTruthy();
  const masters = await mastersResponse.json() as { departments: { id: number; is_active: boolean }[] };
  const department = masters.departments.find((item) => item.is_active);
  expect(department).toBeDefined();
  const departmentId = String(department!.id);

  for (const module of [
    { path: "/fdp", dashboard: "/fdp-dashboard", historicalMessage: /activity start date/i, kpiName: /^Faculty Participated:/ },
    { path: "/certifications", dashboard: "/certification-dashboard", historicalMessage: /completion date/i, kpiName: /^Certifications completed in period:/ },
  ]) {
    await page.goto(module.path);
    await expectUnifiedFilterPanel(page);
    await expectFiltersBeforeKpis(page, module.kpiName);
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
    { path: "/research-projects", category: "SPONSORED_RESEARCH", kpiName: /^Total Research Records:/ },
    { path: "/consultancy", category: "CONSULTANCY", kpiName: /^Total Consultancy Projects:/ },
    { path: "/seed-money", category: "INTERNAL_GRANT", kpiName: /^Total Internal Grants:/ },
  ]) {
    await page.goto(module.path);
    await expectUnifiedFilterPanel(page);
    await expectFiltersBeforeKpis(page, module.kpiName);
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
    await expect(page.getByText(/Activity-Date Department uses verified primary Faculty affiliations at the project sanction date/i)).toBeVisible();
    await page.getByRole("button", { name: "Reset Filters", exact: true }).click();
    await expect(selector).toHaveValue("");
    await expect(attribution).toHaveCount(0);
    await expect(page.getByRole("combobox", { name: "Reporting Period", exact: true })).toHaveValue("This Academic Year");
  }
});

test("Faculty Development and funding filters stay above KPI cards on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const module of [
    { path: "/fdp", kpiName: /^Faculty Participated:/ },
    { path: "/certifications", kpiName: /^Certifications completed in period:/ },
    { path: "/research-projects", kpiName: /^Total Research Records:/ },
    { path: "/consultancy", kpiName: /^Total Consultancy Projects:/ },
    { path: "/seed-money", kpiName: /^Total Internal Grants:/ },
  ]) await expectMobileFilterLayout(page, module.path, module.kpiName);
});

test("mobile custom-date popover stays within the viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/patents");
  await page.getByRole("combobox", { name: "Reporting Period", exact: true }).selectOption("Custom");
  await page.getByRole("button", { name: "Set dates", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Custom date range", exact: true });
  await expect(dialog).toBeVisible();
  const box = await dialog.boundingBox();
  if (!box) throw new Error("Expected a visible custom-date popover");
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(390);
  expect(box.y + box.height).toBeLessThanOrEqual(844);
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
});

test("overview filters use the compact two-column grid on tablet", async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 1024 });
  for (const path of ["/publications", "/patents", "/books", "/fdp", "/certifications", "/research-projects", "/consultancy", "/seed-money"]) {
    await page.goto(path);
    await expectUnifiedFilterPanel(page);
    expect(await page.locator(".overview-filter-grid").evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/).length)).toBe(2);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  }
});

