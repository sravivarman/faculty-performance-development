const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const ts=require('typescript');
const source=ts.transpileModule(fs.readFileSync('lib/books.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const output={exports:{}};new Function('exports','module',source)(output.exports,output);
const {blankBook,blankContributor,bookClaimantReady}=output.exports;
const faculty=(id=1)=>({...blankContributor(1),person_type:'FACULTY',institution_scope:'CURRENT_DEPARTMENT',faculty_id:id,is_claiming_faculty:true});
test('one Faculty claimant with unknown and student contributors is ready',()=>assert.equal(bookClaimantReady({...blankBook(),contributors:[faculty(),blankContributor(2),{...blankContributor(3),person_type:'STUDENT',student_id:1}]}),true));
test('missing claimant is blocked',()=>assert.equal(bookClaimantReady({...blankBook(),contributors:[{...faculty(),is_claiming_faculty:false}]}),false));
for(const person_type of ['UNKNOWN','EXTERNAL_PERSON','STUDENT'])test(`${person_type} cannot claim`,()=>assert.equal(bookClaimantReady({...blankBook(),contributors:[{...faculty(),person_type}]}),false));
test('two Faculty claimants blocked',()=>assert.equal(bookClaimantReady({...blankBook(),contributors:[faculty(),faculty(2)]}),false));
test('chapter editors cannot claim; whole-book editor convention retained',()=>{
 const editor={...faculty(),role:'EDITOR'};
 assert.equal(bookClaimantReady({...blankBook(),work_type:'BOOK_CHAPTER',contributors:[editor]}),false);
 assert.equal(bookClaimantReady({...blankBook(),contributors:[editor]}),true);
});
