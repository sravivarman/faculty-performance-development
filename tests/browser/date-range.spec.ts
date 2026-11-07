import {test,expect} from "@playwright/test";

test.use({timezoneId:"Asia/Kolkata"});

test("presets refresh with inclusive dates, manual edits become Custom, and range carries across reports",async({page})=>{
  await page.clock.install({time:new Date("2026-10-02T12:00:00+05:30")});
  await page.goto('/publications');
  const preset=page.getByRole('combobox',{name:'Reporting Period',exact:true});
  await expect(preset).toHaveValue('This Academic Year');
  await expect(page.getByLabel('From Date',{exact:true})).toHaveCount(0);
  for(const [name,from,to] of [
    ['This Calendar Year','2026-01-01','2026-12-31'],
    ['Last Calendar Year','2025-01-01','2025-12-31'],
    ['This Academic Year','2026-07-01','2027-06-30'],
    ['Last Academic Year','2025-07-01','2026-06-30'],
    ['This Month','2026-10-01','2026-10-31'],
    ['Last Month','2026-09-01','2026-09-30'],
  ]) {
    const refreshed=page.waitForResponse(response=>{
      const url=new URL(response.url());
      return url.pathname==='/api/publication-dashboard' && url.searchParams.get('from_date')===from && url.searchParams.get('to_date')===to;
    });
    await preset.selectOption(name);
    const response=await refreshed;
    expect(response.ok()).toBeTruthy();
    expect(new URL(response.url()).searchParams.has('preset')).toBeFalsy();
    await expect(page.locator('.range-caption')).toContainText(`${from.split('-').reverse().join('-')} to ${to.split('-').reverse().join('-')}`);
  }
  await expect(page.locator('.range-caption')).toContainText('Last Month · 01-09-2026 to 30-09-2026');
  await preset.selectOption('Custom');
  await expect(page.getByLabel('From Date',{exact:true})).toBeVisible();
  await page.getByLabel('From Date',{exact:true}).fill('2026-09-02');
  await expect(preset).toHaveValue('Custom');
  await page.getByRole('button',{name:'Apply range',exact:true}).click();
  for(const [path,title] of [['/','Research overview'],['/patents','Patent overview'],['/books','Books / Chapters overview'],['/publications','Publication overview']]) {
    await page.goto(path);
    await expect(page.getByRole('combobox',{name:'Reporting Period',exact:true})).toHaveValue('Custom');
    await expect(page.getByLabel('From Date',{exact:true})).toHaveValue('2026-09-02');
    await expect(page.getByLabel('To Date',{exact:true})).toHaveValue('2026-09-30');
  }
  await preset.selectOption('Last Academic Year');
  await preset.selectOption('Custom');
  await page.getByLabel('To Date',{exact:true}).fill('2026-06-29');
  await expect(preset).toHaveValue('Custom');
});

test('preset choice persists and recalculates from current application date',async({page})=>{
  await page.clock.install({time:new Date('2026-10-02T12:00:00+05:30')});
  await page.goto('/books');
  const preset=page.getByRole('combobox',{name:'Reporting Period',exact:true});
  await expect(preset).toBeEnabled();
  await preset.selectOption('This Academic Year');
  await page.clock.setSystemTime(new Date('2027-07-01T12:00:00+05:30'));
  await page.getByRole('link',{name:'Patents',exact:true}).click();
  await expect(preset).toHaveValue('This Academic Year');
  await expect(page.getByLabel('From Date',{exact:true})).toHaveCount(0);
  await expect(page.locator('.range-caption')).toContainText('01-07-2027 to 30-06-2028');
  await page.reload();
  await expect(preset).toHaveValue('This Academic Year');
  await expect(page.locator('.range-caption')).toContainText('01-07-2027 to 30-06-2028');
});

