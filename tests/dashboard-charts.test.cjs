const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const ts=require('typescript');
function load(path){const result={exports:{}};const code=ts.transpileModule(fs.readFileSync(path,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;new Function('exports','module','require',code)(result.exports,result,id=>id==='./publication-dashboard'?load('lib/publication-dashboard.ts'):require(id));return result.exports;}
const {trendOption,activityTrendOption,distributionOption,typeLabels,INDEX_DISTRIBUTION,QUARTILES}=load('lib/dashboard-charts.ts');
test('dashboard trend renders backend buckets and keeps every configured series interactive',()=>{
  const option=activityTrendOption({series:{journal:'Journals',conference:'Conferences',patents:'Patents',books:'Books',fdp:'FDP'},unavailable_modules:{fdp:'FDP'},buckets:[{label:'Q1',journal:0,conference:2,patents:0,books:1,fdp:null}]});
  assert.deepEqual(option.xAxis.data,['Q1']);assert.deepEqual(option.series.map(s=>s.data),[[0],[2],[0],[1]]);assert.equal(option.legend.type,'scroll');
});
test('monthly research chart uses existing event-date counts, without summing outcomes',()=>{
  const option=trendOption([{month:'2026-09',publications:5,patents:1,books:2}]);
  assert.deepEqual(option.xAxis.data,['2026-09']);assert.deepEqual(option.series.map(s=>s.data),[[5],[1],[2]]);
  assert.equal(option.legend.bottom,0);
});
test('overlapping indexing is preserved as independent absolute counts',()=>{
  const option=distributionOption(INDEX_DISTRIBUTION,{scie:1,scopus:1,web_of_science:1});
  assert.equal(option.series[0].data.reduce((sum,value)=>sum+value,0),3);
  assert.equal(option.xAxis.type,'value');assert.equal(option.series[0].stack,undefined);
});
test('type and quartile charts use aggregate fields and retain zero categories',()=>{
  assert.deepEqual(distributionOption(typeLabels,{journal:3,conference:2}).series[0].data,[3,2]);
  assert.deepEqual(distributionOption(QUARTILES,{q1:1,quartile_unknown:2}).series[0].data,[1,0,0,0,0,2]);
});
