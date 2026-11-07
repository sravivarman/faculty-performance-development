import {test,expect,type APIRequestContext} from "@playwright/test";

type MasterPerson = {id:number; name:string; employee_id:string};
type MastersPayload = {departments:{id:number;is_active:boolean}[]};

async function activeDepartmentId(request: APIRequestContext) {
  const response=await request.get("/api/masters");
  expect(response.ok()).toBeTruthy();
  const masters=await response.json() as MastersPayload;
  const department=masters.departments.find(value=>value.is_active);
  if(!department) throw new Error("Browser fixtures require an active Department Master record.");
  return department.id;
}

async function createFacultyFixture(request: APIRequestContext, departmentId:number, employeeId:string, name:string):Promise<MasterPerson>{
  const response=await request.post("/api/faculty",{data:{employee_id:employeeId,name,department_id:departmentId,department_effective_from:"2026-07-01"}});
  expect(response.ok()).toBeTruthy();
  return await response.json() as MasterPerson;
}

test("manual review, author ownership, evidence, dashboard and edit",async({page,request})=>{
  const errors:string[]=[];page.on("pageerror",error=>errors.push(error.message));
  const departmentId=await activeDepartmentId(request);
  await page.goto("/masters");
  await page.getByLabel("Employee Id").fill("E2E-A");
  await page.getByLabel("Name",{exact:true}).fill("Faculty A");
  await page.getByLabel("Name Variants").fill("A. Faculty");
  await page.getByLabel("Current Department",{exact:true}).selectOption(String(departmentId));
  await page.getByRole("button",{name:"Save master record"}).click();
  await expect(page.getByRole("status")).toHaveText("Master record saved.");
  await createFacultyFixture(request,departmentId,"E2E-B","Faculty B");
  const studentResponse=await request.post("/api/students",{data:{roll_number:"E2E-X",name:"Student X",department_id:departmentId}});
  expect(studentResponse.ok()).toBeTruthy();
  const student=await studentResponse.json() as {id:number};
  await page.goto("/publications/new");
  await page.getByRole("button",{name:"Enter manually"}).click();
  await page.getByLabel("Title *",{exact:true}).fill("Research collaboration P1");
  await page.getByLabel("DOI",{exact:true}).fill("https://doi.org/10.1234/E2E-P1");
  await page.getByLabel("Publication date *",{exact:true}).fill("2026-09-18");
  await page.getByLabel("Journal name",{exact:true}).fill("Department Research Journal");
  for(const [index,name,type] of [[0,"Faculty A","FACULTY"],[1,"Faculty B","FACULTY"],[2,"Student X","STUDENT"],[3,"External Y","EXTERNAL"]] as const){
    await page.getByRole("button",{name:"+ Add author",exact:true}).click();
    const card=page.locator(".author-card").nth(index);
    await card.getByLabel("Author name",{exact:true}).fill(name);
    await card.getByRole("combobox",{name:"Person Type",exact:true}).selectOption(type);
    if(type==="FACULTY") {
      await card.getByRole("combobox",{name:"Faculty",exact:true}).fill(name);
      await card.getByRole("option",{name:new RegExp(`^${name}\\b`)}).getByRole("button").click();
    }
    if(type==="STUDENT")await card.getByRole("combobox",{name:"Student",exact:true}).selectOption(String(student.id));
  }
  await expect(page.getByRole("radio",{name:"Claiming faculty: Faculty A",exact:true})).toBeChecked();
  await page.getByRole("radio",{name:"Claiming faculty: Faculty B",exact:true}).check();
  await expect(page.getByRole("radio",{name:"Claiming faculty: Faculty A",exact:true})).not.toBeChecked();
  await page.getByRole("radio",{name:"Claiming faculty: Faculty A",exact:true}).check();
  await page.getByLabel("Scopus",{exact:true}).check();
  await page.getByLabel("Choose evidence files").setInputFiles({name:"publication-proof.pdf",mimeType:"application/pdf",buffer:Buffer.from("%PDF-1.4\nproof")});
  await expect(page.getByRole("button",{name:"Save publication",exact:true})).toBeDisabled();
  await page.getByLabel("I reviewed the metadata, author mappings and claiming faculty.").check();
  await page.getByRole("button",{name:"Save publication",exact:true}).click();
  await expect(page).toHaveURL(/\/publications\/\d+$/);
  await expect(page.getByRole("heading",{name:"Research collaboration P1",exact:true})).toBeVisible();
  await expect(page.getByRole("heading",{name:"Evidence · 1 files"})).toBeVisible();
  await expect(page.getByRole("link",{name:"10.1234/e2e-p1 ↗"})).toBeVisible();
  const detailUrl=page.url();
  await page.getByRole("link",{name:"Edit publication",exact:true}).click();
  await page.getByRole("radio",{name:"Claiming faculty: Faculty B",exact:true}).check();
  await page.getByLabel("I reviewed the metadata, author mappings and claiming faculty.").check();
  await page.getByRole("button",{name:"Save changes",exact:true}).click();
  await expect(page).toHaveURL(detailUrl);
  // Keep this dashboard assertion independent of the browser's persisted
  // reporting-period preference and the machine clock.
  await page.goto("/publications?from_date=2026-09-01&to_date=2026-09-30");
  await expect(page.getByRole("button",{name:"Total Publications: 1",exact:true})).toBeVisible();
  await page.getByRole("button",{name:"Publications with Students: 1",exact:true}).first().click();
  await expect(page.locator('#papers').getByRole("link",{name:"Research collaboration P1",exact:true})).toBeVisible();
  await page.getByRole("combobox", { name: "Reporting Period", exact: true }).selectOption("Custom");
  await expect(page.getByLabel("From Date",{exact:true})).toBeVisible();
  await expect(page.getByLabel("To Date",{exact:true})).toBeVisible();
  await page.getByLabel("From Date",{exact:true}).fill("2026-09-01");
  await page.getByLabel("To Date",{exact:true}).fill("2026-09-30");
  await page.getByRole("button",{name:"Apply range",exact:true}).click();
  await expect(page.getByRole("button",{name:"Total Publications: 1",exact:true})).toBeVisible();
  await page.screenshot({path:"test-results/publication-dashboard.png",fullPage:true});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.screenshot({path:"test-results/publication-dashboard-mobile.png",fullPage:true});
  expect(errors).toEqual([]);
});


test("single DOI exception edits return to compact queue without approval",async({page})=>{
  await page.route("**/api/publications/lookup-doi?*",route=>route.fulfill({status:200,json:{doi:"10.1234/queue-preview",title:"Fetched queue preview",publication_type:"JOURNAL",publication_date:"2026-09-18",metadata_source:"CROSSREF",authors:[{author_order:1,author_name_from_source:"Uncertain Faculty",person_type:"UNKNOWN",faculty_id:null,student_id:null,is_internal:false,is_claiming_faculty:false,is_corresponding_author:false,is_first_author:true,affiliation_from_source:[],matching_status:"SUGGESTED",suggestions:[{person_type:"FACULTY",id:1,name:"Faculty A",confidence:.86,reason:"FUZZY"}]}],indexing:[]}}));
  await page.goto('/publications/new');
  await page.getByLabel('DOI or DOI link').fill('https://doi.org/10.1234/queue-preview');
  await page.getByRole('button',{name:'Fetch metadata',exact:true}).click();
  const row=page.getByRole('row',{name:'Fetched queue preview',exact:true});
  await expect(row).toHaveAttribute('data-status','NEEDS_CLAIMANT');
  await expect(page.getByRole('button',{name:'Add All Ready (0)',exact:true})).toBeDisabled();
  await expect(page.locator('.author-card:visible')).toHaveCount(0);
  await row.getByRole('button',{name:'Edit',exact:true}).click();
  const editor=page.getByRole('dialog',{name:'Edit queued publication'});
  await editor.getByRole('button',{name:'Confirm match',exact:true}).click();
  await expect(editor.getByRole('radio',{name:'Claiming faculty: Uncertain Faculty',exact:true})).toBeChecked();
  await editor.getByRole('button',{name:'Return to queue',exact:true}).click();
  await expect(editor).toHaveCount(0);
  await expect(row).toHaveAttribute('data-status','READY_WITH_WARNINGS');
  await expect(page.getByRole('button',{name:'Add All Ready (1)',exact:true})).toBeEnabled();
});

test('unified DOI and BibTeX queue supports inline and selected bulk edits, independent claims and evidence',async({page,request})=>{
  const departmentId=await activeDepartmentId(request);
  const faculty=[
    await createFacultyFixture(request,departmentId,"E2E-Q1","Queue Faculty One"),
    await createFacultyFixture(request,departmentId,"E2E-Q2","Queue Faculty Two"),
  ];
  const authors=faculty.map((f:{id:number;name:string},i:number)=>({author_order:i+1,author_name_from_source:f.name,person_type:'FACULTY',faculty_id:f.id,student_id:null,is_internal:true,is_claiming_faculty:false,is_first_author:i===0,is_corresponding_author:false,affiliation_from_source:[],matching_status:'EXACT'}));
  const unknown={author_order:3,author_name_from_source:'Unclassified colleague',person_type:'UNKNOWN',faculty_id:null,student_id:null,is_internal:false,is_claiming_faculty:false,is_first_author:false,is_corresponding_author:false,affiliation_from_source:['Vardhaman College of Engineering'],matching_status:'UNMATCHED'};
  const existing=await (await request.post('/api/publications',{data:{doi:'10.1234/queue-existing',title:'Existing queue paper',publication_type:'JOURNAL',publication_date:'2026-09-22',indexing:[],authors:[{...authors[0],is_claiming_faculty:true}]}})).json();
  let active=0,maximum=0;const calls:string[]=[];
  await page.route('**/api/publications/lookup-doi?*',async route=>{
    const doi=new URL(route.request().url()).searchParams.get('doi')!;calls.push(doi);active++;maximum=Math.max(maximum,active);
    await new Promise(resolve=>setTimeout(resolve,40));active--;
    if(doi===existing.doi)return route.fulfill({status:409,json:{detail:{message:'Publication already exists.',publication_id:existing.id}}});
    if(doi.endsWith('/queue-fetch-failed'))return route.fulfill({status:502,json:{detail:'One provider failure'}});
    return route.fulfill({status:200,json:{doi,title:`Queue ${doi}`,publication_type:doi.endsWith('/queue-conference')?'CONFERENCE':'JOURNAL',journal_conference_name:'Queue venue',conference_name:'Queue Conference',publication_date:'2026-09-22',metadata_source:'CROSSREF',authors:[...(doi.endsWith('/queue-conference')?authors:[authors[0]]),unknown],indexing:[]}});
  });
  let fail=true;
  await page.route('**/api/publications',route=>route.request().method()==='POST' && route.request().postDataJSON().doi==='10.1234/queue-save-failed' && fail?route.fulfill({status:500,json:{detail:'One save failure'}}):route.continue());
  await page.goto('/publications/new');
  await page.getByLabel('DOI or DOI link').fill('10.1234/queue-one\nhttps://doi.org/10.1234/QUEUE-ONE;10.1234/queue-conference,10.1234/queue-save-failed;10.1234/queue-fetch-failed;10.1234/queue-existing;invalid');
  await page.getByRole('button',{name:'Fetch metadata',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'Metadata retrieval complete: 6 of 6 processed'})).toBeVisible();
  expect(maximum).toBe(1);expect(calls).toHaveLength(5);
  const one=page.getByRole('row',{name:'Queue 10.1234/queue-one',exact:true});
  const conference=page.getByRole('row',{name:'Queue 10.1234/queue-conference',exact:true});
  await expect(one).toHaveAttribute('data-status','READY_WITH_WARNINGS');
  await expect(one.getByRole('combobox',{name:'Claiming faculty',exact:true})).toHaveValue(String(faculty[0].id));
  await expect(conference).toHaveAttribute('data-status','NEEDS_CLAIMANT');
  await conference.getByRole('combobox',{name:'Claiming faculty',exact:true}).selectOption(String(faculty[1].id));
  await conference.getByRole('combobox',{name:'Quartile',exact:true}).selectOption('NOT_APPLICABLE');
  await expect(page.locator('.author-card:visible')).toHaveCount(0);
  await one.getByRole('checkbox').first().check();await conference.getByRole('checkbox').first().check();
  await page.getByText(/Bulk edit selected rows/).click();
  await page.getByRole('button',{name:'Add indexing to selected',exact:true}).click();
  await page.getByRole('combobox',{name:'Bulk classification',exact:true}).selectOption('INTERNATIONAL');
  await page.getByRole('button',{name:'Set classification for selected',exact:true}).click();
  await one.locator('td').nth(10).locator('summary').click();
  await one.getByLabel('Scie',{exact:true}).check();await one.getByLabel('Web Of Science',{exact:true}).check();
  await one.getByLabel('Impact factor',{exact:true}).fill('3.7');await one.getByRole('combobox',{name:'Quartile',exact:true}).selectOption('Q1');
  await conference.getByRole('button',{name:'Edit',exact:true}).click();
  const editor=page.getByRole('dialog',{name:'Edit queued publication'});
  await editor.getByRole('combobox',{name:'Evidence type',exact:true}).selectOption('CERTIFICATE');
  await editor.getByLabel('Choose evidence files').setInputFiles({name:'certificate.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-1.4 certificate')});
  await editor.getByRole('button',{name:'Return to queue',exact:true}).click();
  await page.getByRole('button',{name:'BibTeX',exact:true}).click();
  await page.getByLabel('Enrich missing fields using DOI metadata').uncheck();
  await page.getByLabel('BibTeX content').fill(`@article{queuebib, title={Queue BibTeX Journal},author={${faculty[0].name}},journal={Bibtex Venue},date={2026-09-22}}
@inproceedings{queueconf, title={Queue BibTeX Conference},author={${faculty[0].name}},booktitle={Bibtex Proceedings},date={2026-09-22}}
@article{partial,title={Queue Partial Date},author={${faculty[0].name}},year={2026}}
`);
  await page.getByRole('button',{name:'Parse BibTeX',exact:true}).click();
  await expect(page.getByRole('row',{name:'Queue BibTeX Journal',exact:true})).toHaveAttribute('data-status','READY_WITH_WARNINGS');
  await expect(page.getByRole('row',{name:'Queue Partial Date',exact:true})).toHaveAttribute('data-status','NEEDS_METADATA');
  await expect(page.getByRole('button',{name:'Add All Ready (5)',exact:true})).toBeEnabled();
  await one.getByRole('button',{name:'Add',exact:true}).click();
  await expect(one).toHaveAttribute('data-status','SAVED');
  await page.getByRole('button',{name:'Add All Ready (4)',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'3 publication(s) added. 1 operation(s) need attention'})).toBeVisible();
  await expect(conference).toHaveAttribute('data-status','SAVED');
  fail=false;await page.getByRole('button',{name:'Add All Ready (1)',exact:true}).click();
  await expect(page.getByRole('button',{name:'Add All Ready (0)',exact:true})).toBeDisabled();
  const saved=await (await request.get('/api/publications')).json();
  const journal=saved.find((p:{doi:string})=>p.doi==='10.1234/queue-one');
  const conf=saved.find((p:{doi:string})=>p.doi==='10.1234/queue-conference');
  expect(journal.indexing).toEqual(['SCOPUS','SCIE','WEB_OF_SCIENCE']);expect(journal.classification).toBe('INTERNATIONAL');
  expect(conf.classification).toBe('INTERNATIONAL');expect(conf.indexing).toEqual(['SCOPUS']);expect(conf.quartile).toBe('NOT_APPLICABLE');expect(conf.impact_factor).toBeNull();expect(conf.evidence_count).toBe(1);
  expect(conf.authors.find((a:{is_claiming_faculty:boolean})=>a.is_claiming_faculty).faculty_id).toBe(faculty[1].id);expect(conf.authors.at(-1).person_type).toBe('UNKNOWN');
  await page.getByRole('combobox',{name:'Filter classification',exact:true}).selectOption('INTERNATIONAL');
  await expect(page.locator('.import-queue tbody tr')).toHaveCount(2);
  await page.getByRole('combobox',{name:'Filter classification',exact:true}).selectOption('');
  await page.getByRole('combobox',{name:'Filter queue',exact:true}).selectOption('DUPLICATE');await expect(page.locator('.import-queue tbody tr')).toHaveCount(1);
  await page.getByRole('combobox',{name:'Filter queue',exact:true}).selectOption('ALL');
  await page.screenshot({path:'test-results/import-queue.png',fullPage:true});
  for(const pub of saved.filter((p:{doi:string;title:string})=>p.doi?.startsWith('10.1234/queue-') || p.title.startsWith('Queue BibTeX'))) expect((await request.delete(`/api/publications/${pub.id}`)).ok()).toBeTruthy();
});

test("publication quality fields follow the selected publication type", async ({ page }) => {
  await page.goto("/publications/new");
  await page.getByRole("button", { name: "Enter manually", exact: true }).click();
  const type = page.getByRole("combobox", { name: "Publication type", exact: true });
  await type.selectOption("JOURNAL");
  await expect(page.getByRole("combobox", { name: "Conference Scope", exact: true })).toHaveCount(0);
  await expect(page.getByRole("combobox", { name: "Quartile", exact: true })).toBeVisible();
  await expect(page.getByRole("spinbutton", { name: "Impact factor", exact: true })).toBeVisible();
  await type.selectOption("CONFERENCE");
  await expect(page.getByRole("combobox", { name: "Conference Scope", exact: true })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Quartile", exact: true })).toHaveCount(0);
  await expect(page.getByRole("spinbutton", { name: "Impact factor", exact: true })).toHaveCount(0);
});
