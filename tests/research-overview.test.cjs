const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const ts=require('typescript');
const source=ts.transpileModule(fs.readFileSync('lib/research-overview.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
const loaded={exports:{}};
new Function('exports','require','module',source)(loaded.exports,require,loaded);
const {currency,moduleLink}=loaded.exports;
test('Indian currency grouping keeps sanctioned and received amounts individually formatted',()=>{
  assert.equal(currency(12345678),'₹1,23,45,678');
  assert.equal(currency(0),'₹0');
});
test('module drill links preserve explicit inclusive bounds, faculty and event',()=>{
  const bounds={from_date:'2026-09-01',to_date:'2026-09-30'};
  const url=new URL(moduleLink('patents','granted',bounds,{drill_faculty_id:'7'}),'http://localhost');
  assert.equal(url.pathname,'/patents');
  assert.equal(url.searchParams.get('metric'),'granted');
  assert.equal(url.searchParams.get('drill_faculty_id'),'7');
  assert.equal(url.searchParams.get('from_date'),bounds.from_date);
  assert.equal(url.searchParams.get('to_date'),bounds.to_date);
  assert.equal(url.searchParams.has('preset'),false);
});
