import { expect, test } from "@playwright/test";

test("publication report builder exposes table and citation configuration", async ({ page }) => {
  await page.goto("/publications/reports");
  const reportBuilder = page.getByRole("main");

  await expect(reportBuilder.getByRole("heading", { name: "Report Builder", exact: true })).toBeVisible();
  await expect(reportBuilder.getByRole("button", { name: "Custom Table Report", exact: true })).toBeVisible();
  await expect(reportBuilder.getByRole("button", { name: "Citation List", exact: true })).toBeVisible();
  await expect(reportBuilder.getByRole("combobox", { name: "Publication Type", exact: true })).toHaveValue("ALL");
  const scope = reportBuilder.getByRole("combobox", { name: "Reporting Scope", exact: true });
  await expect(scope).toHaveValue("INSTITUTION");
  await expect(reportBuilder.getByRole("combobox", { name: "Department", exact: true })).toHaveCount(0);
  await scope.selectOption("DEPARTMENT");
  await expect(reportBuilder.getByRole("combobox", { name: "Department", exact: true })).toBeVisible();
  await expect(reportBuilder.getByRole("combobox", { name: "Department Attribution", exact: true })).toBeVisible();
  await scope.selectOption("FACULTY");
  await expect(reportBuilder.getByRole("combobox", { name: "Faculty", exact: true })).toBeVisible();
  await expect(reportBuilder.getByRole("combobox", { name: "Faculty Relationship", exact: true })).toHaveValue("CLAIMING");
  await scope.selectOption("INSTITUTION");
  await expect(reportBuilder.getByRole("combobox", { name: "Row Mode", exact: true })).toHaveValue("PUBLICATION");
  await expect(reportBuilder.getByRole("textbox", { name: "Find Faculty", exact: true })).toBeVisible();
  const indexing = reportBuilder.getByRole("combobox", { name: "Indexing", exact: true });
  await expect(indexing).toHaveValue("");
  await indexing.selectOption("SCOPUS");
  await expect(indexing).toHaveValue("SCOPUS");
  await indexing.selectOption("WEB_OF_SCIENCE");
  await expect(indexing).toHaveValue("WEB_OF_SCIENCE");
  await indexing.selectOption("");
  await expect(reportBuilder.getByRole("button", { name: "Clear report filters", exact: true })).toBeVisible();
  const facultyGrid = reportBuilder.locator(".report-faculty-list");
  await expect.poll(() => facultyGrid.evaluate((element) => getComputedStyle(element).gridTemplateColumns.split(" ").length)).toBe(4);
  await page.setViewportSize({ width: 900, height: 720 });
  await expect.poll(() => facultyGrid.evaluate((element) => getComputedStyle(element).gridTemplateColumns.split(" ").length)).toBe(2);
  await page.setViewportSize({ width: 640, height: 720 });
  await expect.poll(() => facultyGrid.evaluate((element) => getComputedStyle(element).gridTemplateColumns.split(" ").length)).toBe(1);
  await page.setViewportSize({ width: 1280, height: 720 });
  await expect(reportBuilder.getByRole("checkbox", { name: /Article Number/ })).toBeVisible();
  await expect(reportBuilder.getByRole("checkbox", { name: "Conference Scope Stored", exact: true })).toBeVisible();
  await expect(reportBuilder.getByRole("checkbox", { name: "SCI Indexed Calculated", exact: true })).toBeVisible();
  await expect(reportBuilder.getByText("Conference Type", { exact: true })).toHaveCount(0);
  for (const removedField of ["Starting Page", "Ending Page", "Conference Acronym", "Funding Acknowledgement", "Funded Publication", "Corresponding Institution"]) {
    await expect(reportBuilder.getByText(removedField, { exact: true })).toHaveCount(0);
  }

  const publicationType = reportBuilder.getByRole("combobox", { name: "Publication Type", exact: true });
  await publicationType.selectOption("JOURNAL");
  await expect(reportBuilder.getByRole("checkbox", { name: "Conference Scope Stored", exact: true })).toHaveCount(0);
  await expect(reportBuilder.getByRole("combobox", { name: "Journal Quartile", exact: true })).toBeVisible();
  await publicationType.selectOption("CONFERENCE");
  await expect(reportBuilder.getByRole("checkbox", { name: "Conference Scope Stored", exact: true })).toBeVisible();
  await expect(reportBuilder.getByRole("combobox", { name: "Journal Quartile", exact: true })).toHaveCount(0);

  await reportBuilder.getByRole("combobox", { name: "Reporting Period", exact: true }).selectOption("CUSTOM");
  await expect(reportBuilder.locator("#report-from-date")).toBeVisible();
  await expect(reportBuilder.locator("#report-to-date")).toBeVisible();

  await reportBuilder.getByRole("button", { name: "Citation List", exact: true }).click();
  await expect(reportBuilder.getByRole("combobox", { name: "Citation Style", exact: true })).toHaveValue("IEEE");
  await expect(reportBuilder.getByText("Items missing a title are excluded by default", { exact: false })).toBeVisible();
});
