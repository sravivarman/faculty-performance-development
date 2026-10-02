const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const ts=require('typescript');
function load(path,dependencies={}) {
  const source=ts.transpileModule(fs.readFileSync(path,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  const module={exports:{}};
  new Function('require','exports','module',source)(name=>dependencies[name],module.exports,module);
  return module.exports;
}
const api=load('lib/api.ts');
const {doiReadiness,isSaveable,authorWarnings,prepareQueuePublication,queueReadiness}=load('lib/publication-readiness.ts',{'./api':api});
const author=(kind,claim=false)=>({...api.blankAuthor(1),author_name_from_source:kind,person_type:kind,faculty_id:kind==='FACULTY'?1:null,student_id:kind==='STUDENT'?1:null,is_claiming_faculty:claim,matching_status:'EXACT'});
const paper=(authors)=>({...api.blankPublication(),doi:'10.1234/paper',title:'Paper',publication_date:'2026-09-22',authors});
for(const [name,others,expected] of [
  ['UNKNOWN',[author('UNKNOWN')],'READY_WITH_WARNINGS'],
  ['EXTERNAL',[author('EXTERNAL')],'READY'],
  ['STUDENT and UNKNOWN',[author('STUDENT'),author('UNKNOWN')],'READY_WITH_WARNINGS'],
  ['only Faculty',[],'READY'],
  ['four UNKNOWN',Array.from({length:4},()=>author('UNKNOWN')),'READY_WITH_WARNINGS'],
]) test(`Faculty claimant with ${name}`,()=>assert.equal(doiReadiness(paper([author('FACULTY',true),...others]),true),expected));
test('no claimant is blocked',()=>assert.equal(doiReadiness(paper([author('FACULTY'),author('UNKNOWN')]),true),'NEEDS_CLAIMANT'));
for(const kind of ['UNKNOWN','STUDENT','EXTERNAL']) test(`${kind} cannot claim`,()=>assert.equal(doiReadiness(paper([author(kind,true)]),true),'INVALID'));
test('two claimants rejected',()=>assert.equal(doiReadiness(paper([author('FACULTY',true),{...author('FACULTY',true),faculty_id:2}]),true),'INVALID'));
test('review remains required',()=>assert.equal(doiReadiness(paper([author('FACULTY',true),author('UNKNOWN')]),false),'AUTHOR_REVIEW'));
test('invalid bibliographic and KPI fields block saving',()=>{
  for(const change of [{title:' '},{publication_date:'2026-02-30'},{publication_type:'OTHER'},{impact_factor:-1},{quartile:'Q9'}]) assert.equal(doiReadiness({...paper([author('FACULTY',true)]),...change},true),'INVALID');
});
test('nine DOI records count READY and warning rows, excluding saved and blocked',()=>{
  const records=Array.from({length:9},(_,index)=>paper([author('FACULTY',index<8),...(index>=6?[author('UNKNOWN')]:[])]));
  assert.equal(records.filter(p=>isSaveable(doiReadiness(p,true))).length,8);
  for(let index=0;index<8;index++) records[index].id=index+1;
  assert.equal(records.filter(p=>isSaveable(doiReadiness(p,true))).length,0);
});
test('duplicates stay blocked',()=>assert.equal(doiReadiness(paper([author('FACULTY',true),author('UNKNOWN')]),true,true),'DUPLICATE'));
test('Vardhaman unknown warning is informational',()=>{
  const p=paper([author('FACULTY',true),{...author('UNKNOWN'),affiliation_from_source:['Vardhaman College of Engineering, EEE']}]);
  assert.equal(doiReadiness(p,true),'READY_WITH_WARNINGS');
  assert.ok(authorWarnings(p).some(w=>w.includes('UNRESOLVED_INTERNAL_AUTHOR')));
});

test('queue auto-claims a sole mapped faculty without approval',()=>{
  const p=prepareQueuePublication(paper([author('FACULTY'),author('UNKNOWN')]));
  assert.equal(p.authors[0].is_claiming_faculty,true);
  assert.equal(queueReadiness(p),'READY_WITH_WARNINGS');
  assert.equal(p.classification,'UNKNOWN');
  assert.equal(p.impact_factor,undefined);
});
test('queue multiple faculty require explicit claimant',()=>{
  const p=prepareQueuePublication(paper([author('FACULTY'),{...author('FACULTY'),faculty_id:2}]));
  assert.equal(queueReadiness(p),'NEEDS_CLAIMANT');
});
test('queue BibTeX without DOI is valid and classification is independent',()=>{
  const p=prepareQueuePublication({...paper([author('FACULTY')]),doi:null,source_type:'BIBTEX',classification:'INTERNATIONAL',indexing:['SCIE','SCOPUS','WEB_OF_SCIENCE']});
  assert.equal(queueReadiness(p),'READY_WITH_WARNINGS');
  assert.deepEqual(p.indexing,['SCIE','SCOPUS','WEB_OF_SCIENCE']);
  assert.equal(p.classification,'INTERNATIONAL');
});
test('queue missing dates block, unknown classification does not',()=>{
  const p=prepareQueuePublication(paper([author('FACULTY')]));
  assert.ok(isSaveable(queueReadiness(p)));
  assert.equal(queueReadiness({...p,publication_date:''}),'NEEDS_METADATA');
  assert.equal(queueReadiness({...p,classification:'Publisher guess'}),'INVALID');
});
