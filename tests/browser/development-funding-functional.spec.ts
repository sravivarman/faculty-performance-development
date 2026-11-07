import { expect, test } from "@playwright/test";

async function chooseFaculty(page: import("@playwright/test").Page, label: string, name: string) {
  const selector = page.getByRole("combobox", { name: label, exact: true });
  await selector.fill(name);
  await page.getByRole("button", { name: new RegExp(`^${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`) }).click();
}

async function createFaculty(request: import("@playwright/test").APIRequestContext, employeeId: string, name: string) {
  const response = await request.post("/api/faculty", { data: { employee_id: employeeId, name } });
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json() as Promise<{ id: number; name: string }>;
}

test("FDP activity can be created, evidenced, edited, deactivated, and reactivated through the browser", async ({ page, request }) => {
  const faculty = await createFaculty(request, "E2E-FDP-1", "Functional FDP Faculty");
  await page.goto("/fdp/new");
  await page.getByRole("textbox", { name: /Activity title/ }).fill("Functional FDP Activity");
  await page.getByRole("textbox", { name: /Organizing Institution/ }).fill("VCE");
  await page.getByLabel(/Start date/).fill("2026-09-18");
  await page.getByRole("button", { name: "+ Add Faculty", exact: true }).click();
  await chooseFaculty(page, "Participant 1", faculty.name);
  await page.getByRole("combobox", { name: "Participation role", exact: true }).selectOption("COORDINATOR");
  await page.getByRole("button", { name: "Save activity", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Functional FDP Activity", exact: true })).toBeVisible();
  await expect(page.getByText("Coordinator", { exact: true })).toBeVisible();

  await page.getByLabel("Choose document").setInputFiles({ name: "fdp-proof.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 FDP proof") });
  await page.getByRole("button", { name: "Upload evidence", exact: true }).click();
  await expect(page.getByText("fdp-proof.pdf", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "Edit activity", exact: true }).click();
  await page.getByRole("textbox", { name: /Activity title/ }).fill("Functional FDP Activity Updated");
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Functional FDP Activity Updated", exact: true })).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Deactivate", exact: true }).click();
  await expect(page.getByText(/Activity deactivated/i)).toBeVisible();
  await page.getByRole("button", { name: "Reactivate", exact: true }).click();
  await expect(page.getByRole("link", { name: "Edit activity", exact: true })).toBeVisible();
});

test("Certification creation, in-progress edit semantics, and evidence use the saved record", async ({ page, request }) => {
  const faculty = await createFaculty(request, "E2E-CERT-1", "Functional Certification Faculty");
  await page.goto("/certifications/new");
  await chooseFaculty(page, "Faculty", faculty.name);
  await page.getByRole("textbox", { name: "Course / certification name" }).fill("Functional MOOC");
  await page.getByRole("textbox", { name: "Provider / Issuer" }).fill("NPTEL");
  await page.getByRole("combobox", { name: "Category", exact: true }).selectOption("MOOC");
  await page.getByRole("textbox", { name: "Completion date" }).fill("2026-09-18");
  await page.getByRole("button", { name: "Save certification", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Functional MOOC", exact: true })).toBeVisible();
  await page.getByLabel("Choose document").setInputFiles({ name: "credential.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 credential") });
  await page.getByRole("button", { name: "Upload evidence", exact: true }).click();
  await expect(page.getByText("credential.pdf", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "Edit certification", exact: true }).click();
  await page.getByRole("combobox", { name: "Status", exact: true }).selectOption("IN_PROGRESS");
  await expect(page.getByText(/does not require a completion date/i)).toBeVisible();
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(page.getByText("In Progress", { exact: true })).toBeVisible();
  await expect(page.getByText("credential.pdf", { exact: true })).toBeVisible();
});

test("Sponsored research uses browser-created Faculty investigators, financial values, evidence, and lifecycle controls", async ({ page, request }) => {
  const faculty = await createFaculty(request, "E2E-FUND-1", "Functional Funding Faculty");
  await page.goto("/research-projects/new");
  await page.getByRole("textbox", { name: /Project title/ }).fill("Functional Sponsored Project");
  await page.getByLabel("Recorded Lead / Administrative Department *").fill("EEE");
  await page.getByRole("combobox", { name: "Project status *", exact: true }).selectOption("SANCTIONED");
  await page.getByLabel("Sanction / approval date").fill("2026-09-18");
  await page.getByLabel("Sanctioned amount (INR)").fill("1000000.00");
  await page.getByRole("button", { name: /Add investigator/ }).click();
  await chooseFaculty(page, "Member Principal Investigator 1", faculty.name);
  await page.getByRole("button", { name: "Save project", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Functional Sponsored Project", exact: true })).toBeVisible();
  await expect(page.getByText("Member PI", { exact: true })).toBeVisible();
  await page.getByLabel("Choose document").setInputFiles({ name: "sanction.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 sanction") });
  await page.getByRole("button", { name: "Upload evidence", exact: true }).click();
  await expect(page.getByText("sanction.pdf", { exact: true })).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Deactivate", exact: true }).click();
  await expect(page.getByRole("button", { name: "Reactivate", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Reactivate", exact: true }).click();
  await expect(page.getByRole("link", { name: "Edit record", exact: true })).toBeVisible();
});
