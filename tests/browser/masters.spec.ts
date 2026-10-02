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
