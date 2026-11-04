import {test,expect} from "@playwright/test";

test("editing Faculty Master preserves weak variant review safeguards",async({page,request})=>{
  const response=await request.post("/api/faculty",{data:{employee_id:"VARIANT-TEST",name:"Dr. Md. Asif Test",designation:"Professor",name_variants:["Md Asif Test","Md. Asif Test","M. Asif Test"],name_variant_strengths:{"M. Asif Test":"WEAK"}}});
  expect(response.ok()).toBeTruthy();const faculty=await response.json();
  await page.goto("/masters");
  const row=page.getByRole("row").filter({hasText:"VARIANT-TEST"});
  await row.getByRole("button",{name:"Edit",exact:true}).click();
  await expect(page.getByLabel("Weak aliases (review required)",{exact:true})).toHaveValue("M. Asif Test");
  await page.getByLabel("Designation",{exact:true}).fill("Associate Professor");
  await page.getByRole("button",{name:"Save master record",exact:true}).click();
  await expect(page.getByRole("status")).toHaveText("Master record saved.");
  const result=await (await request.get("/api/masters")).json();
  const updated=result.faculty.find((p:{id:number})=>p.id===faculty.id);
  expect(updated.name).toBe("Dr. Md. Asif Test");
  expect(updated.designation).toBe("Associate Professor");
  expect(updated.name_variants).toEqual(["Md Asif Test","M. Asif Test"]);
  expect(updated.name_variant_strengths["m asif test"]).toBe("WEAK");
});

test("unused Master records require confirmation before permanent deletion", async ({ page, request }) => {
  const created = await request.post("/api/faculty", { data: { employee_id: "DELETE-TEST", name: "Delete Test Faculty" } });
  expect(created.ok()).toBeTruthy();
  const faculty = await created.json();

  await page.goto("/masters");
  const row = page.getByRole("row").filter({ hasText: "DELETE-TEST" });
  await row.getByRole("button", { name: "Delete", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Delete Faculty Member?" });
  await expect(dialog).toContainText("Delete Test Faculty");
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(row).toBeVisible();

  await row.getByRole("button", { name: "Delete", exact: true }).click();
  await dialog.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("was deleted");
  await expect(row).toHaveCount(0);
  const masters = await (await request.get("/api/masters")).json();
  expect(masters.faculty.some((person: { id: number }) => person.id === faculty.id)).toBeFalsy();
});

test("Department Master lifecycle, Faculty transfer and protected deletion work through Masters", async ({ page }) => {
  const code = "BROWSER-DEPT";
  await page.goto("/masters");
  await page.getByRole("button", { name: "Departments", exact: true }).click();
  await page.getByLabel("Code", { exact: true }).fill(code);
  await page.getByLabel("Name", { exact: true }).fill("Browser Department");
  await page.getByRole("button", { name: "Save master record", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("Master record saved.");

  const departmentRow = page.getByRole("row").filter({ hasText: code });
  await departmentRow.getByRole("button", { name: "Edit", exact: true }).click();
  await page.getByLabel("Name", { exact: true }).fill("Browser Department Updated");
  await page.getByRole("button", { name: "Save master record", exact: true }).click();
  await expect(departmentRow).toContainText("Browser Department Updated");

  await page.getByRole("button", { name: "Faculty", exact: true }).click();
  await page.getByLabel("Employee Id", { exact: true }).fill("BROWSER-DEPT-F");
  await page.getByLabel("Name", { exact: true }).fill("Browser Department Faculty");
  const currentDepartment = page.getByRole("combobox", { name: "Current Department", exact: true });
  await expect(currentDepartment).toBeVisible();
  await currentDepartment.selectOption({ label: "Browser Department Updated (BROWSER-DEPT)" });
  await page.getByLabel("Department effective from", { exact: true }).fill("2026-07-01");
  await page.getByRole("button", { name: "Save master record", exact: true }).click();

  const facultyRow = page.getByRole("row").filter({ hasText: "BROWSER-DEPT-F" });
  await expect(facultyRow).toContainText("Browser Department Updated");
  await facultyRow.getByRole("button", { name: "Edit", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Department history", exact: true })).toBeVisible();
  const transferDepartment = page.getByRole("combobox", { name: "Transfer to Department", exact: true });
  await expect(transferDepartment).toBeVisible();
  await transferDepartment.selectOption({ label: "Electrical and Electronics Engineering (EEE)" });
  await page.getByLabel("Transfer effective from", { exact: true }).fill("2027-07-01");
  await page.getByRole("button", { name: "Transfer Department", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Faculty Department transferred");

  await page.getByRole("button", { name: "Departments", exact: true }).click();
  const protectedRow = page.getByRole("row").filter({ hasText: code });
  await protectedRow.getByRole("button", { name: "Delete", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Delete Department?" });
  await dialog.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("Faculty department affiliations");
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();

  await protectedRow.getByRole("button", { name: "Deactivate", exact: true }).click();
  await expect(protectedRow).toContainText("Inactive");
  await protectedRow.getByRole("button", { name: "Reactivate", exact: true }).click();
  await expect(protectedRow).toContainText("Active");
});
