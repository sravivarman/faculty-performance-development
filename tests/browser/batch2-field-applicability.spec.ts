import { expect, test } from "@playwright/test";

test("Batch 2 labels and conditional fields follow the selected record type", async ({ page }) => {
  await page.goto("/patents/new");
  await expect(page.getByRole("textbox", { name: "Jurisdiction / Country", exact: true })).toBeVisible();
  await expect(page.getByRole("textbox", { name: /^Applicant \/ Assignee/ })).toBeVisible();
  await expect(page.getByText("Enter the recorded applicant or assignee information as stated in the patent document.", { exact: true })).toBeVisible();

  await page.goto("/books/new");
  await page.getByRole("button", { name: "Manual Entry", exact: true }).click();
  await expect(page.getByRole("combobox", { name: "Classification", exact: true })).toHaveCount(0);
  await page.getByRole("combobox", { name: "Type", exact: true }).selectOption("BOOK_CHAPTER");
  await expect(page.getByRole("combobox", { name: "Classification", exact: true })).toHaveCount(0);

  await page.goto("/fdp/new");
  const activityType = page.getByRole("combobox", { name: /^Activity type/ });
  for (const type of ["FDP", "STTP", "WORKSHOP", "WEBINAR", "SEMINAR"]) {
    await activityType.selectOption(type);
    await expect(page.getByRole("textbox", { name: "Host Organization Location", exact: true })).toHaveCount(0);
  }
  await expect(page.getByRole("textbox", { name: /^Organizing Institution \/ Organization/ })).toBeVisible();
  await activityType.selectOption("INTERNSHIP");
  await expect(page.getByRole("textbox", { name: "Host Organization Location", exact: true })).toBeVisible();
  await expect(page.getByRole("textbox", { name: /^Host Organization \/ Company/ })).toBeVisible();
  await activityType.selectOption("INDUSTRIAL_TRAINING");
  await expect(page.getByRole("textbox", { name: "Host Organization Location", exact: true })).toBeVisible();
  await activityType.selectOption("FDP");
  await page.getByRole("combobox", { name: "Mode", exact: true }).selectOption("ONLINE");
  await expect(page.getByRole("textbox", { name: "Location / venue", exact: true })).toHaveCount(0);

  await page.goto("/certifications/new");
  await expect(page.getByRole("textbox", { name: "Provider / Issuer", exact: true })).toBeVisible();

  await page.goto("/research-projects/new");
  await expect(page.getByRole("textbox", { name: "Recorded Lead / Administrative Department *", exact: true })).toBeVisible();
  await expect(page.getByText("This records the Department stated for project administration. Participating Departments are determined separately from linked Faculty investigators.", { exact: true })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Funding Agency", exact: true })).toBeVisible();

  await page.goto("/consultancy/new");
  await expect(page.getByRole("textbox", { name: "Client / Sponsoring Organization", exact: true })).toBeVisible();

  await page.goto("/seed-money/new");
  await expect(page.getByRole("textbox", { name: "Internal Granting Authority / Institution", exact: true })).toBeVisible();
});
