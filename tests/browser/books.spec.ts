import {test,expect} from "@playwright/test";

async function chooseFaculty(card: import("@playwright/test").Locator, name: string) {
  const selector = card.getByRole("combobox", {name: "Faculty", exact: true});
  await selector.fill(name);
  await card.getByRole("button", {name: new RegExp(`^${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`)}).click();
}

async function applyCustomRange(page: import("@playwright/test").Page, from: string, to: string) {
  await page.getByRole("combobox", {name: "Reporting Period", exact: true}).selectOption("Custom");
  await expect(page.getByLabel("From Date", {exact: true})).toBeVisible();
  await page.getByLabel("From Date", {exact: true}).fill(from);
  await page.getByLabel("To Date", {exact: true}).fill(to);
  await page.getByRole("button", {name: "Apply range", exact: true}).click();
}

test("book chapter entry, contributors, evidence, counting and date-preserving drilldowns",async({page,request})=>{
  const create=async(path:string,data:object)=>{const response=await request.post(`/api${path}`,{data});expect(response.ok()).toBeTruthy();return response.json();};
  await create("/faculty",{employee_id:"BOOK-A",name:"Book Faculty A"});
  await create("/faculty",{employee_id:"BOOK-B",name:"Book Faculty B"});
  await create("/faculty",{employee_id:"BOOK-C",name:"Book Faculty C"});
  await create("/students",{roll_number:"BOOK-X",name:"Book Student X"});
  await page.goto("/books/new");
  await page.getByRole("button",{name:"Manual Entry",exact:true}).click();
  await expect(page.getByLabel("Chapter number",{exact:true})).toHaveCount(0);
  await page.getByRole("combobox",{name:"Type",exact:true}).selectOption("BOOK_CHAPTER");
  await page.getByLabel("Title *",{exact:true}).fill("Chapter B1: Power Systems");
  await page.getByLabel("Parent book title *",{exact:true}).fill("Engineering Handbook");
  await page.getByLabel("Publisher *",{exact:true}).fill("Engineering Press");
  await page.getByLabel("Publication date *",{exact:true}).fill("2026-08-15");
  await page.getByLabel("Page range *",{exact:true}).fill("15–28");
  await page.getByLabel("ISBN",{exact:true}).fill("978-0-306-40615-7");
  const contributors=[{name:"Book Faculty A",type:"FACULTY"},{name:"Book Faculty B",type:"FACULTY"},{name:"Book Faculty C",type:"FACULTY"},{name:"Book Student X",type:"STUDENT"},{name:"External Author Y",type:"EXTERNAL_PERSON"}];
  for(const [index,c] of contributors.entries()){
    await page.getByRole("button",{name:"+ Add contributor",exact:true}).click();const card=page.locator(".contributor-card").nth(index);
    await card.getByLabel("Contributor name",{exact:true}).fill(c.name);
    await card.getByRole("combobox",{name:"Person Type",exact:true}).selectOption(c.type);
    if(c.type==="FACULTY")await chooseFaculty(card,c.name);
    if(c.type==="STUDENT")await card.getByRole("combobox",{name:"Student",exact:true}).selectOption({label:c.name});
    if(c.type==="EXTERNAL_PERSON")await card.getByLabel("Organization / Institution",{exact:true}).fill("External University");
  }
  await page.getByRole("radio",{name:"Claiming faculty: Book Faculty A",exact:true}).check();
  await page.getByRole("radio",{name:"Claiming faculty: Book Faculty B",exact:true}).check();
  await expect(page.getByRole("radio",{name:"Claiming faculty: Book Faculty A",exact:true})).not.toBeChecked();
  await page.getByRole("radio",{name:"Claiming faculty: Book Faculty A",exact:true}).check();
  await expect(page.getByRole("radio",{name:"Claiming faculty: Book Faculty C",exact:true})).toBeEnabled();
  await page.getByLabel("Choose evidence files").setInputFiles([{name:"cover.pdf",mimeType:"application/pdf",buffer:Buffer.from("%PDF-1.4 cover")},{name:"chapter.pdf",mimeType:"application/pdf",buffer:Buffer.from("%PDF-1.4 chapter")}]);
  await page.getByLabel("I reviewed the dates, contributor affiliations and claimant.").check();
  await page.getByRole("button",{name:"Save Book / Chapter",exact:true}).click();
  await expect(page).toHaveURL(/\/books\/\d+$/);
  const detail=page.url();const id=detail.split("/").pop();
  await expect(page.getByRole("heading",{name:"Evidence · 2 files"})).toBeVisible();
  await expect(page.getByText("Claiming Faculty",{exact:true})).toBeVisible();
  await page.getByRole("link",{name:"Edit work",exact:true}).click();
  await expect(page.getByLabel("Page range *",{exact:true})).toHaveValue("15–28");
  await page.locator(".contributor-card").nth(1).getByRole("combobox",{name:"Role",exact:true}).selectOption("EDITOR");
  await expect(page.getByRole("radio",{name:"Claiming faculty: Book Faculty B",exact:true})).toBeDisabled();
  await page.locator(".contributor-card").nth(1).getByRole("combobox",{name:"Role",exact:true}).selectOption("AUTHOR");
  await page.getByLabel("I reviewed the dates, contributor affiliations and claimant.").check();
  await page.getByRole("button",{name:"Save book changes",exact:true}).click();await expect(page).toHaveURL(detail);
  await page.goto("/books?from_date=2026-07-01&to_date=2026-09-30");
  await page.getByText("Collaboration and authorship indicators",{exact:true}).click();
  for(const title of ["Total Works","Book Chapters","Student-involved","Works with External Collaboration","Unique Department Student Authors"]){await expect(page.getByRole("button",{name:`${title}: 1`,exact:true})).toBeVisible();}
  await expect(page.getByRole("button",{name:"Books: 0",exact:true})).toBeVisible();
  await expect(page.getByRole("button",{name:"Unique Department Faculty Authors: 3",exact:true})).toBeVisible();
  const facultyPanel=page.locator("section").filter({has:page.getByRole("heading",{name:"Faculty contributions",exact:true})});
  const rowB=facultyPanel.getByRole("row").filter({hasText:"Book Faculty B"});
  await expect(rowB.locator(".link-button")).toHaveText(["0","0","0","1","0","1","1"]);
  await rowB.getByRole("button").last().click();
  await expect(page.locator("#book-records tbody tr")).toHaveCount(1);
  await page.locator("#book-records").getByRole("link",{name:"View Details →",exact:true}).click();
  await expect(page).toHaveURL(/from_date=2026-07-01/);
  await page.getByRole("link",{name:"← Back to report",exact:true}).click();
  await expect(page.getByLabel("From Date",{exact:true})).toHaveValue("2026-07-01");
  await page.screenshot({path:"test-results/books-dashboard.png",fullPage:true});
  await applyCustomRange(page,"2026-08-15","2026-08-15");
  await expect(page.getByRole("button",{name:"Total Works: 1",exact:true})).toBeVisible();
  const record=await (await request.get(`/api/books/${id}`)).json();
  expect(record.contributors).toHaveLength(5);expect(record.evidence_count).toBe(2);
  await page.getByRole("link",{name:"Overview",exact:true}).click();
  await page.getByRole("button",{name:"Books / Chapters: 1",exact:true}).click();
  await expect(page.getByLabel("From Date",{exact:true})).toHaveValue("2026-08-15");
});

test("manual book entry without ISBN requires a Faculty claimant",async({page,request})=>{
  const faculty = await (await request.post("/api/faculty", {data: {employee_id: "BOOK-CLAIMANT", name: "Book Faculty Claimant"}})).json();
  await page.goto("/books/new");
  await page.getByRole("button",{name:"Manual Entry",exact:true}).click();
  await page.getByLabel("Title *",{exact:true}).fill("An older engineering book");
  await page.getByLabel("Publisher *",{exact:true}).fill("Archive Press");
  await page.getByLabel("Publication date *",{exact:true}).fill("1990-01-01");
  await page.getByLabel("Edition",{exact:true}).fill("First");
  await page.getByRole("button",{name:"+ Add contributor",exact:true}).click();
  await page.getByLabel("Contributor name",{exact:true}).fill("Unresolved editor");
  await page.getByRole("combobox",{name:"Role",exact:true}).selectOption("EDITOR");
  await page.getByLabel("I reviewed the dates, contributor affiliations and claimant.").check();
  await expect(page.getByRole("button",{name:"Save Book / Chapter",exact:true})).toBeDisabled();
  await page.getByRole("button",{name:"+ Add contributor",exact:true}).click();
  const card=page.locator(".contributor-card").last();
  await card.getByLabel("Contributor name",{exact:true}).fill(faculty.name);
  await card.getByRole("combobox",{name:"Person Type",exact:true}).selectOption("FACULTY");
  await chooseFaculty(card,faculty.name);
  await card.getByRole("radio",{name:`Claiming faculty: ${faculty.name}`,exact:true}).check();
  await page.getByLabel("I reviewed the dates, contributor affiliations and claimant.").check();
  await page.getByRole("button",{name:"Save Book / Chapter",exact:true}).click();
  await expect(page).toHaveURL(/\/books\/\d+$/);
  await expect(page.getByRole("heading",{name:"An older engineering book",exact:true})).toBeVisible();
  await expect(page.getByText("First",{exact:true})).toBeVisible();
});
