import {test,expect} from "@playwright/test";

test("patent affiliations, one-record lifecycle, evidence and date-specific grant drill-down",async({page,request})=>{
  const create=async(path:string,data:object)=>{const response=await request.post(`/api${path}`,{data});expect(response.ok()).toBeTruthy();return response.json();};
  const faculty=await create("/faculty",{employee_id:"PAT-A",name:"Patent Faculty A"});
  await create("/faculty",{employee_id:"PAT-B",name:"Patent Faculty B"});
  await create("/students",{roll_number:"PAT-X",name:"Patent Student X"});
  await page.goto("/patents/new");
  await page.getByRole("combobox",{name:"Patent Type",exact:true}).selectOption("UTILITY");
  await page.getByLabel("Patent title *",{exact:true}).fill("Adaptive energy storage patent");
  await page.getByLabel("Application number",{exact:true}).fill(" EEE / 2026 - 123 ");
  await page.getByLabel("Filing date",{exact:true}).fill("2026-08-10");
  const inventors=[{name:"Patent Faculty A",type:"FACULTY",scope:"CURRENT_DEPARTMENT"},{name:"Patent Faculty B",type:"FACULTY",scope:"CURRENT_DEPARTMENT"},{name:"Patent Student X",type:"STUDENT",scope:"CURRENT_DEPARTMENT"},{name:"Collaborator CSE",type:"FACULTY",scope:"SAME_INSTITUTION_OTHER_DEPARTMENT"},{name:"External Inventor",type:"EXTERNAL_PERSON",scope:"EXTERNAL_INSTITUTION"}];
  for(const [index,inventor] of inventors.entries()){
    await page.getByRole("button",{name:"+ Add inventor",exact:true}).click();const card=page.locator(".inventor-card").nth(index);
    await card.getByLabel("Inventor name",{exact:true}).fill(inventor.name);
    await card.getByRole("combobox",{name:"Person type",exact:true}).selectOption(inventor.type);
    await card.getByRole("combobox",{name:"Affiliation",exact:true}).selectOption(inventor.scope);
    if(inventor.scope==="CURRENT_DEPARTMENT")await card.getByRole("combobox",{name:"Local master reference",exact:true}).selectOption({label:inventor.name});
    if(inventor.scope==="SAME_INSTITUTION_OTHER_DEPARTMENT")await card.getByLabel("Department / Organization",{exact:true}).fill("CSE");
    if(inventor.scope==="EXTERNAL_INSTITUTION")await card.getByLabel("Institution name",{exact:true}).fill("IIT Hyderabad");
  }
  await expect(page.getByRole("checkbox",{name:"Claiming faculty: Patent Faculty A",exact:true})).toBeChecked();
  await expect(page.getByRole("checkbox",{name:"Claiming faculty: Collaborator CSE",exact:true})).toBeDisabled();
  await page.getByRole("checkbox",{name:"Claiming faculty: Patent Faculty B",exact:true}).check();
  await page.getByLabel("Choose evidence files").setInputFiles({name:"filing.pdf",mimeType:"application/pdf",buffer:Buffer.from("%PDF-1.4 filing")});
  await page.getByLabel("I reviewed the dates, inventor affiliations and claimants.").check();
  await page.getByRole("button",{name:"Save patent",exact:true}).click();
  await expect(page).toHaveURL(/\/patents\/\d+$/);const detail=page.url();const identity=detail.split("/").pop();
  await expect(page.getByRole("heading",{name:"Evidence · 1 files"})).toBeVisible();
  await expect(page.getByText("IIT Hyderabad",{exact:false})).toBeVisible();
  await page.getByRole("link",{name:"Edit patent",exact:true}).click();
  await page.getByLabel("Publication number",{exact:true}).fill("PUB-123");await page.getByLabel("Publication date",{exact:true}).fill("2026-12-15");
  await page.getByRole("combobox",{name:"Current status",exact:true}).selectOption("PUBLISHED");
  await page.getByLabel("I reviewed the dates, inventor affiliations and claimants.").check();await page.getByRole("button",{name:"Save patent changes",exact:true}).click();await expect(page).toHaveURL(detail);
  await page.getByRole("link",{name:"Edit patent",exact:true}).click();
  await page.getByLabel("Grant number",{exact:true}).fill("GR-123");await page.getByLabel("Grant date",{exact:true}).fill("2027-08-12");
  await page.getByRole("combobox",{name:"Current status",exact:true}).selectOption("GRANTED");
  await page.getByLabel("I reviewed the dates, inventor affiliations and claimants.").check();await page.getByRole("button",{name:"Save patent changes",exact:true}).click();await expect(page).toHaveURL(detail);
  const record=await (await request.get(`/api/patents/${identity}`)).json();expect(record.status_history.map((h:{new_status:string})=>h.new_status)).toEqual(["FILED","PUBLISHED","GRANTED"]);expect(record.inventors.find((i:{is_claiming_faculty:boolean})=>i.is_claiming_faculty).faculty_id).toBe(faculty.id);
  await page.goto("/patents?from_date=2026-07-01&to_date=2027-06-30");
  await expect(page.getByRole("button",{name:"Unique Patents: 1",exact:true})).toBeVisible();
  await expect(page.getByRole("button",{name:"Granted: 0",exact:true})).toBeVisible();
  await expect(page.getByRole("button",{name:"Interdepartmental: 1",exact:true})).toBeVisible();
  await page.getByLabel("From Date",{exact:true}).fill("2027-08-12");await page.getByLabel("To Date",{exact:true}).fill("2027-08-12");await page.getByRole("button",{name:"Apply dates",exact:true}).click();
  await expect(page.getByRole("button",{name:"Unique Patents: 1",exact:true})).toBeVisible();
  await page.getByRole("button",{name:"Granted: 1",exact:true}).click();await expect(page.getByRole("link",{name:"Adaptive energy storage patent",exact:true})).toBeVisible();
  await page.screenshot({path:"test-results/patent-dashboard.png",fullPage:true});
  await page.getByRole("link",{name:"Publications",exact:true}).click();await expect(page.getByLabel("From Date",{exact:true})).toHaveValue("2027-08-12");
  await page.getByRole("link",{name:"Overview",exact:true}).click();await page.getByRole("button",{name:"Patents: 1",exact:true}).click();await page.getByRole("button",{name:"Granted: 1",exact:true}).click();
  await expect(page).toHaveURL(/metric=granted/);await expect(page.getByRole("link",{name:"Adaptive energy storage patent",exact:true})).toBeVisible();
  await page.goto("/patents/new");await page.getByRole("combobox",{name:"Patent Type",exact:true}).selectOption("UTILITY");await page.getByLabel("Patent title *",{exact:true}).fill("Duplicate check");await page.getByLabel("Application number",{exact:true}).fill("eee2026123");await page.getByLabel("I reviewed the dates, inventor affiliations and claimants.").check();await page.getByRole("button",{name:"Save patent",exact:true}).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Patent already exists");await expect(page.getByRole("link",{name:"Open existing patent →"})).toHaveAttribute("href",`/patents/${identity}`);
});

test("date range rejects reversed bounds and presets refresh explicit dates",async({page})=>{
  await page.goto("/patents?from_date=2026-07-01&to_date=2027-06-30");
  await page.getByLabel("From Date",{exact:true}).fill("2028-01-01");await page.getByLabel("To Date",{exact:true}).fill("2027-01-01");await page.getByRole("button",{name:"Apply dates",exact:true}).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("From Date must be on or before To Date");
  await page.getByRole("combobox",{name:"Date Range",exact:true}).selectOption("This Academic Year");
  await expect(page.getByLabel("From Date",{exact:true})).toHaveValue(/\d{4}-07-01/);await expect(page.getByLabel("To Date",{exact:true})).toHaveValue(/\d{4}-06-30/);
  await page.getByRole("button",{name:"Apply dates",exact:true}).click();await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
});
