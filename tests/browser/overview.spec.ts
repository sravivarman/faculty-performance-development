import {test,expect} from '@playwright/test';

test('executive overview counts, filters, charts, faculty drills and restored context',async({page,request})=>{
  await page.clock.install({time:new Date('2026-10-02T12:00:00+05:30')});
  const faculty=[];
  for(const name of ['Overview Claimant','Overview Coauthor']){
    const result=await request.post('/api/faculty',{data:{employee_id:name,name}});expect(result.ok()).toBeTruthy();faculty.push(await result.json());
  }
  const student=await (await request.post('/api/students',{data:{roll_number:'OVERVIEW-STUDENT',name:'Overview Student'}})).json();
  const ids:number[]=[];
  try{
    for(let i=0;i<5;i++){
      const response=await request.post('/api/publications',{data:{title:`Overview paper ${i}`,doi:`10.1234/overview-${i}`,publication_type:i<3?'JOURNAL':'CONFERENCE',publication_date:'2026-09-18',journal_conference_name:'Overview Journal',conference_name:i>=3?'Overview Conference':null,indexing:i===0?['SCIE','SCOPUS','WEB_OF_SCIENCE']:['UNKNOWN'],quartile:i===0?'Q1':'UNKNOWN',classification:'INTERNATIONAL',authors:[
        {author_order:1,author_name_from_source:faculty[0].name,person_type:'FACULTY',faculty_id:faculty[0].id,is_claiming_faculty:true},
        {author_order:2,author_name_from_source:faculty[1].name,person_type:'FACULTY',faculty_id:faculty[1].id},
        {author_order:3,author_name_from_source:'Overview Student',person_type:'STUDENT',student_id:student.id},
        {author_order:4,author_name_from_source:'Unclassified',person_type:'UNKNOWN',affiliation_from_source:['Vardhaman College']},
      ]}});expect(response.ok()).toBeTruthy();ids.push((await response.json()).id);
    }
    await page.goto('/publications?from_date=2026-09-01&to_date=2026-09-30');
    await expect(page.getByRole('button',{name:'Total Publications: 5',exact:true})).toBeVisible();
    await expect(page.getByRole('button',{name:'Faculty Claimants: 1',exact:true})).toBeVisible();
    await page.getByRole('button',{name:'Scopus: 1',exact:true}).click();
    await expect(page.locator('#papers').getByRole('heading')).toContainText('1 papers');
    await expect(page.locator('#papers').getByRole('link',{name:'Overview paper 0',exact:true})).toBeVisible();
    await page.getByRole('button',{name:'Overview Coauthor Q1: 1',exact:true}).click();
    await expect(page.locator('#papers').getByRole('heading')).toContainText('1 papers');
    expect(new URL(page.url()).searchParams.get('drill_faculty_id')).toBe(String(faculty[1].id));
    await page.getByRole('button',{name:'Publication Classification · International: 5',exact:true}).click();
    await expect(page.locator('#papers').getByRole('heading')).toContainText('5 papers');
    await page.getByRole('combobox',{name:'Publication Type',exact:true}).selectOption('CONFERENCE');
    await expect(page.getByRole('button',{name:'Total Publications: 2',exact:true})).toBeVisible();
    await page.getByRole('button',{name:'View All Publications',exact:true}).click();
    await expect(page.locator('#papers').getByRole('heading')).toContainText('2 papers');
    await page.locator('#papers').getByRole('link',{name:'Overview paper 4',exact:true}).click();
    await expect(page.getByRole('heading',{name:'Overview paper 4',exact:true})).toBeVisible();
    await page.goBack();
    await expect(page.getByRole('combobox',{name:'Publication Type',exact:true})).toHaveValue('CONFERENCE');
    await page.reload();
    await expect(page.getByRole('combobox',{name:'Publication Type',exact:true})).toHaveValue('CONFERENCE');
    await expect(page.locator('#papers').getByRole('heading')).toContainText('2 papers');
    await page.getByRole('button',{name:'Reset Filters',exact:true}).click();
    await expect(page.getByRole('button',{name:'Total Publications: 5',exact:true})).toBeVisible();
    const preset=page.getByRole('combobox',{name:'Date Range',exact:true});
    await preset.selectOption('Last Calendar Year');
    await expect(page.getByRole('button',{name:'Total Publications: 0',exact:true})).toBeVisible();
    await preset.selectOption('This Calendar Year');
    await expect(page.getByRole('button',{name:'Total Publications: 5',exact:true})).toBeVisible();
    await page.getByText('Explore monthly records',{exact:true}).click();
    await page.getByRole('button',{name:'2026-09 total: 5',exact:true}).click();
    await expect(page.locator('#papers').getByRole('heading')).toContainText('5 papers');
    await preset.selectOption('This Month');
    await expect(page.locator('#papers').getByRole('heading')).toContainText('0 papers');
    await preset.selectOption('Last Month');
    await expect(page.getByRole('button',{name:'Total Publications: 5',exact:true})).toBeVisible();
    await page.getByRole('button',{name:'Reset Filters',exact:true}).click();
    await page.screenshot({path:'test-results/executive-overview.png',fullPage:true});
    await page.setViewportSize({width:390,height:844});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
    await page.screenshot({path:'test-results/executive-overview-mobile.png',fullPage:true});
    await page.getByRole('link',{name:'Overview',exact:true}).click();
    await expect(page.getByRole('heading',{name:'Research Overview',exact:true})).toBeVisible();
  }finally{for(const id of ids)await request.delete(`/api/publications/${id}`);}
});

