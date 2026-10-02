const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const ts=require('typescript');
const source=ts.transpileModule(fs.readFileSync('lib/date-range.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const output={exports:{}};
new Function('exports','module',source)(output.exports,output);
const {presetRange,validRange,displayRange}=output.exports;
const october=new Date(2026,9,2);
for(const [preset,from_date,to_date] of [
  ['This Calendar Year','2026-01-01','2026-12-31'],
  ['Last Calendar Year','2025-01-01','2025-12-31'],
  ['This Academic Year','2026-07-01','2027-06-30'],
  ['Last Academic Year','2025-07-01','2026-06-30'],
  ['This Month','2026-10-01','2026-10-31'],
  ['Last Month','2026-09-01','2026-09-30'],
]) test(`October: ${preset}`,()=>assert.deepEqual(presetRange(preset,october),{from_date,to_date}));
test('March current and last academic years',()=>{
  const today=new Date(2026,2,14);
  assert.deepEqual(presetRange('This Academic Year',today),{from_date:'2025-07-01',to_date:'2026-06-30'});
  assert.deepEqual(presetRange('Last Academic Year',today),{from_date:'2024-07-01',to_date:'2025-06-30'});
});
test('academic year changes on July 1',()=>{
  assert.deepEqual(presetRange('This Academic Year',new Date(2026,5,30)),{from_date:'2025-07-01',to_date:'2026-06-30'});
  assert.deepEqual(presetRange('This Academic Year',new Date(2026,6,1)),{from_date:'2026-07-01',to_date:'2027-06-30'});
});
test('December to January transition and last month crosses year',()=>{
  assert.deepEqual(presetRange('This Month',new Date(2026,11,31)),{from_date:'2026-12-01',to_date:'2026-12-31'});
  assert.deepEqual(presetRange('This Month',new Date(2027,0,1)),{from_date:'2027-01-01',to_date:'2027-01-31'});
  assert.deepEqual(presetRange('Last Month',new Date(2027,0,1)),{from_date:'2026-12-01',to_date:'2026-12-31'});
});
test('leap February and last February',()=>{
  assert.deepEqual(presetRange('This Month',new Date(2028,1,15)),{from_date:'2028-02-01',to_date:'2028-02-29'});
  assert.deepEqual(presetRange('Last Month',new Date(2028,2,1)),{from_date:'2028-02-01',to_date:'2028-02-29'});
  assert.equal(presetRange('This Month',new Date(2027,1,15)).to_date,'2027-02-28');
});
test('years are calculated rather than fixed',()=>assert.deepEqual(presetRange('Last Academic Year',new Date(2034,0,2)),{from_date:'2032-07-01',to_date:'2033-06-30'}));
test('ranges validate actual dates, inclusive single days and ordering',()=>{
  assert.ok(validRange({from_date:'2028-02-29',to_date:'2028-02-29'}));
  for(const range of [null,{}, {from_date:'2027-02-29',to_date:'2027-03-01'},{from_date:'2026-12-01',to_date:'2026-01-01'}]) assert.equal(validRange(range),false);
});
test('display uses resolved day-month-year boundaries',()=>assert.equal(displayRange(presetRange('Last Academic Year',october)),'01-07-2025 to 30-06-2026'));
test('Custom and unsupported labels cannot silently become a month',()=>{
  assert.throws(()=>presetRange('Custom',october),RangeError);
  assert.throws(()=>presetRange('typo',october),RangeError);
});
