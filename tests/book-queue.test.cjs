const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const ts=require('typescript');
const output={exports:{}};new Function('exports','module',ts.transpileModule(fs.readFileSync('lib/book-queue.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText)(output.exports,output);
const {readyItems,queueSummary}=output.exports;
const row=(status,key=1)=>({key,status,doi:'10.1234/'+key,retrieved:true,typeResolved:true,draft:{work_type:'BOOK_CHAPTER'},selected:false});
test('bulk readiness includes only currently unsaved validated READY rows',()=>assert.deepEqual(readyItems([row('READY',1),row('NEEDS_CLAIMANT',2),row('SAVED',3),{...row('READY',4),validating:true},{...row('READY',5),draft:{id:5}}]).map(r=>r.key),[1]));
test('summary separates failures, duplicates, source types and saves',()=>{
 const rows=[row('READY',1),{...row('SAVED',2),draft:{id:2,work_type:'BOOK'}},{...row('DUPLICATE',3),retrieved:false},{...row('LOOKUP_FAILED',4),retrieved:false},{...row('INVALID_DOI',5),doi:null,retrieved:false},row('NEEDS_CLAIMANT',6)];
 assert.deepEqual(queueSummary(rows),{'Input DOIs':6,'Valid DOIs':5,'Metadata retrieved':3,'Books detected':1,'Book Chapters detected':2,'Ready':1,'Saved':1,'Duplicates':1,'Failed lookups':1,'Needs review':2});
});
test('individually saved row and retries cannot enter bulk readiness',()=>{const r=row('READY');assert.equal(readyItems([r]).length,1);r.status='SAVED';r.draft.id=1;assert.equal(readyItems([r]).length,0);});
