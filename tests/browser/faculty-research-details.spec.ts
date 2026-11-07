import { expect, test } from "@playwright/test";

test("Faculty Research Details keeps a complete profile and exposes a scoped Department context", async ({ page, request }) => {
  const masters = await (await request.get("/api/masters")).json() as { departments: { id: number; code: string; is_active: boolean }[] };
  const department = masters.departments.find((item) => item.is_active);
  expect(department).toBeDefined();
  const facultyResponse = await request.post("/api/faculty", { data: {
    employee_id: "FRD-E2E-1", name: "Faculty Profile E2E", department_id: department!.id,
    department_effective_from: "2025-07-01",
  } });
  expect(facultyResponse.ok(), await facultyResponse.text()).toBeTruthy();
  const faculty = await facultyResponse.json() as { id: number; name: string };
  const publicationResponse = await request.post("/api/publications", { data: {
    doi: "10.1234/faculty-profile-e2e", title: "Faculty Profile Publication", publication_type: "JOURNAL",
    publication_date: "2026-09-18", journal_conference_name: "VCE Journal", indexing: [],
    authors: [{ author_order: 1, author_name_from_source: faculty.name, person_type: "FACULTY", faculty_id: faculty.id, is_internal: true, is_claiming_faculty: true }],
  } });
  expect(publicationResponse.ok(), await publicationResponse.text()).toBeTruthy();

  await page.goto("/?from_date=2026-07-01&to_date=2026-12-31");
  await page.getByRole("button", { name: "Open Faculty Research Details: Faculty Profile E2E", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Faculty Research Details" });
  await expect(dialog).toContainText(`(${department!.code})`);
  await expect(dialog.getByRole("combobox", { name: "Reporting context", exact: true })).toHaveValue("COMPLETE");
  await dialog.getByRole("combobox", { name: "Reporting context", exact: true }).selectOption("DEPARTMENT");
  const scopeDepartment = dialog.getByRole("combobox", { name: "Department", exact: true });
  await expect(scopeDepartment.locator(`option[value="${department!.id}"]`)).toHaveCount(1);
  await Promise.all([
    page.waitForResponse((response) => {
      const url = new URL(response.url());
      return url.pathname.endsWith(`/research/faculty/${faculty.id}`) && url.searchParams.get("department_id") === String(department!.id);
    }),
    scopeDepartment.selectOption(String(department!.id)),
  ]);
  await expect(dialog).toContainText(/Only this Faculty member's own linked records are included/i);
  await dialog.getByRole("combobox", { name: "Attribution", exact: true }).selectOption("AT_ACTIVITY_DATE");
  await expect(dialog).toContainText(/without a verifiable dated affiliation/i);
  await dialog.getByRole("tab", { name: "Publications", exact: true }).click();
  await expect(dialog.getByRole("link", { name: "Faculty Profile Publication", exact: true })).toBeVisible();
});
