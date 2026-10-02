import {test,expect} from '@playwright/test';

test('research overview uses shared dates, missing modules, faculty activity view and module drills',async({page,request})=>{
  const faculty=await (await request.post('/api/faculty',{data:{employee_id:'RESEARCH-E2E',name:'Research Faculty'}})).json();
  const publication=await (await request.post('/api/publications',{data:{title:'Research overview fixture',doi:'10.1234/research-overview-e2e',publication_type:'JOURNAL',publication_date:'2026-09-18',journal_conference_name:'Research Journal',indexing:['SCOPUS'],quartile:'Q1',classification:'INTERNATIONAL',authors:[{author_order:1,author_name_from_source:'Research Faculty',person_type:'FACULTY',faculty_id:faculty.id,is_claiming_faculty:true}]}})).json();
  try{
    await page.goto('/?from_date=2026-09-18&to_date=2026-09-18');
    const response=await request.get('/api/research/overview?from_date=2026-09-18&to_date=2026-09-18');expect(response.ok()).toBeTruthy();const report=await response.json();
    await expect(page.getByRole('button',{name:`Journals: ${report.outcomes.journal}`,exact:true})).toBeVisible();
    await expect(page.getByRole('button',{name:'Research Proposals: Not configured',exact:true})).toBeEnabled();
    await page.getByRole('button',{name:'Open Faculty Research Details: Research Faculty',exact:true}).click();
    const modal=page.getByRole('dialog',{name:'Faculty Research Details'});
    await expect(modal).toContainText('RESEARCH-E2E');
    await expect(modal).toContainText('2026-09-18 to 2026-09-18');
    await modal.getByRole('tab',{name:'Publications',exact:true}).click();
    await expect(modal.getByRole('link',{name:'Research overview fixture',exact:true})).toBeVisible();
    await modal.getByRole('button',{name:'Close Faculty Research Details'}).click();
    await page.getByRole('button',{name:'Research Faculty Publications Authored: 1',exact:true}).click();
    await expect(page).toHaveURL(/\/publications\?/);
    expect(new URL(page.url()).searchParams.get('from_date')).toBe('2026-09-18');
    expect(new URL(page.url()).searchParams.get('to_date')).toBe('2026-09-18');
    await expect(page.locator('#papers').getByRole('link',{name:'Research overview fixture',exact:true})).toBeVisible();
    await page.goBack();
    await expect(page.getByRole('heading',{name:'Research Overview',exact:true})).toBeVisible();
    await expect(page.getByLabel('From Date',{exact:true})).toHaveValue('2026-09-18');
    await expect(page.getByRole('button',{name:`Journals: ${report.outcomes.journal}`,exact:true})).toBeVisible();
    await page.screenshot({path:'test-results/research-overview.png',fullPage:true});
    await page.setViewportSize({width:390,height:844});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
    await page.screenshot({path:'test-results/research-overview-mobile.png',fullPage:true});
  }finally{await request.delete(`/api/publications/${publication.id}`);}
});
