import {test,expect} from '@playwright/test';
test('shared faculty profile, chart drill-down and module dashboards preserve identity and dates',async({page,request})=>{
  const create=async(path:string,data:object)=>{const response=await request.post(`/api${path}`,{data});expect(response.ok(),await response.text()).toBeTruthy();return response.json();};
  const a=await create('/faculty',{employee_id:'ROLLOUT-A',name:'Rollout Claimant'});
  const b=await create('/faculty',{employee_id:'ROLLOUT-B',name:'Rollout Coauthor',designation:'Professor'});
  const authors=[{author_order:1,author_name_from_source:a.name,person_type:'FACULTY',faculty_id:a.id,is_claiming_faculty:true},{author_order:2,author_name_from_source:b.name,person_type:'FACULTY',faculty_id:b.id},{author_order:3,author_name_from_source:'Unknown source author',person_type:'UNKNOWN'}];
  const p=await create('/publications',{doi:'10.1234/rollout-profile',title:'Rollout publication',publication_type:'JOURNAL',publication_date:'2026-09-18',journal_conference_name:'Research Journal',indexing:['SCI','SCOPUS'],quartile:'Q1',classification:'INTERNATIONAL',authors});
  const past=await create('/publications',{doi:'10.1234/rollout-history',title:'Rollout history',publication_type:'CONFERENCE',publication_date:'2025-09-18',journal_conference_name:'Research Conference',conference_name:'Research Conference',indexing:['UNKNOWN'],authors});
  const patent=await create('/patents',{title:'Rollout patent',application_number:'ROLLOUT2026',patent_office:'Indian Patent Office',patent_type:'UTILITY',current_status:'GRANTED',filing_date:'2026-03-01',publication_date:'2026-04-01',grant_date:'2027-02-01',inventors:[{inventor_order:1,inventor_name:a.name,person_type:'FACULTY',institution_scope:'CURRENT_DEPARTMENT',faculty_id:a.id,is_claiming_faculty:true},{inventor_order:2,inventor_name:b.name,person_type:'FACULTY',institution_scope:'CURRENT_DEPARTMENT',faculty_id:b.id}]});
  const book=await create('/books',{work_type:'BOOK',title:'Rollout book',publisher:'University Press',publication_date:'2026-09-18',contributors:[{contributor_order:1,contributor_name:a.name,role:'AUTHOR',person_type:'FACULTY',institution_scope:'CURRENT_DEPARTMENT',faculty_id:a.id,is_claiming_faculty:true},{contributor_order:2,contributor_name:b.name,role:'EDITOR',person_type:'FACULTY',institution_scope:'CURRENT_DEPARTMENT',faculty_id:b.id}]});
  const dates='from_date=2026-01-01&to_date=2026-12-31';
  try{
    for(const path of ['/','/publications','/patents','/books']){
      await page.goto(`${path}?${dates}`);
      await page.getByRole('button',{name:'Open Faculty Research Details: Rollout Coauthor',exact:true}).click();
      const modal=page.getByRole('dialog',{name:'Faculty Research Details'});
      await expect(modal).toContainText('ROLLOUT-B');await expect(modal).toContainText('Professor');await expect(modal).toContainText('2026-01-01 to 2026-12-31');
      await expect(modal.locator('.dash-profile-summary > div').filter({has:page.getByText('Publications Claimed',{exact:true})}).locator('strong')).toHaveText('0');
      await expect(modal.locator('.dash-profile-summary > div').filter({has:page.getByText('Publications Authored',{exact:true})}).locator('strong')).toHaveText('1');
      await modal.getByRole('tab',{name:'Publications',exact:true}).click();
      await expect(modal.getByRole('link',{name:'Rollout publication',exact:true})).toBeVisible();await expect(modal).toContainText('Co-author');await expect(modal.getByRole('link',{name:'Rollout history',exact:true})).toHaveCount(0);
      await modal.getByRole('tab',{name:'Patents',exact:true}).click();await expect(modal.getByRole('link',{name:'Rollout patent',exact:true})).toBeVisible();await expect(modal).toContainText('Inventor');
      await modal.getByRole('tab',{name:'Books / Chapters',exact:true}).click();await expect(modal.getByRole('link',{name:'Rollout book',exact:true})).toHaveAttribute('href',`/books/${book.id}?${dates}`);
      await page.keyboard.press('Escape');await expect(modal).not.toBeVisible();
    }
    await page.goto(`/?${dates}`);await expect(page.locator('[data-chart-ready=true]')).toHaveCount(5);
    await expect(page.getByRole('combobox',{name:'Calendar Year'})).toBeEnabled();
    const yearResponse=page.waitForResponse(r=>r.url().includes('calendar_year=2025')&&r.status()===200);
    await page.getByRole('combobox',{name:'Calendar Year'}).selectOption('2025');const yearReport=await (await yearResponse).json();expect(yearReport.buckets).toHaveLength(12);expect(yearReport.calendar_year).toBe(2025);
    await page.getByRole('combobox',{name:'Calendar Year'}).selectOption('2026');
    // Click the actual ECharts bar, not the alternative keyboard drill-down link.
    await page.locator('figure[aria-label="Publications by Type"] svg path[fill="#2563eb"]').first().click();
    await expect(page).toHaveURL(/\/publications\?.*metric=journal/);expect(new URL(page.url()).searchParams.get('from_date')).toBe('2026-01-01');
    await expect(page.locator('#papers').getByRole('link',{name:'Rollout publication',exact:true})).toBeVisible();
  }finally{await request.delete(`/api/publications/${p.id}`);await request.delete(`/api/publications/${past.id}`);await request.delete(`/api/patents/${patent.id}`);await request.delete(`/api/books/${book.id}`);}
});

test('unconfigured dashboards share presets and never fetch invented module data',async({page})=>{
  const calls:string[]=[];page.on('request',r=>{if(r.url().includes('/api/'))calls.push(r.url());});
  for(const [path,title] of [['fdp','FDP / Workshop / Seminar Overview'],['certifications','Certifications Overview'],['proposals','Research Proposals Overview'],['consultancy','Consultancy Overview']]){
    await page.goto(`/${path}?from_date=2026-03-01&to_date=2026-03-31`);await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible();await expect(page.getByText('Not configured',{exact:true}).first()).toBeVisible();await expect(page.getByLabel('From Date',{exact:true})).toHaveValue('2026-03-01');
    await page.getByRole('combobox',{name:'Date Range',exact:true}).selectOption('This Academic Year');await page.getByRole('button',{name:'Reset',exact:true}).click();
    await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  }
  expect(calls).toEqual([]);
});

test('publication analytics API failure stays local to its tiles',async({page})=>{
  await page.route('**/api/publication-dashboard?*',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Analytics temporarily unavailable'})}));
  await page.goto('/?from_date=2026-01-01&to_date=2026-12-31');await expect(page.getByRole('heading',{name:'Research Overview',exact:true})).toBeVisible();await expect(page.getByRole('button',{name:/^Journals: \d+$/})).toBeEnabled();await expect(page.getByRole('heading',{name:'Faculty Research Contribution',exact:true})).toBeVisible();await expect(page.getByRole('alert').first()).toContainText('Analytics temporarily unavailable');
});
