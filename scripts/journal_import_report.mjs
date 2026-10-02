import fs from 'node:fs/promises';
import { Workbook, SpreadsheetFile } from 'file:///C:/Users/silic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';

const directory = process.argv[2];
const outputDir = process.argv[3];
const report = JSON.parse(await fs.readFile(`${directory}/import-reconciliation.json`, 'utf8'));
if (!report.validation || report.rows.length !== 138) throw Error('Complete validated import report required');
const workbook = Workbook.create();
const summary = workbook.worksheets.add('Summary');
const detail = workbook.worksheets.add('Import rows');
const v = report.validation;
for (const sheet of [summary, detail]) {
  sheet.showGridLines = false;
  sheet.tabColor = '#253D5B';
}
summary.getRange('A2').values = [['Historical journal import']];
summary.getRange('A2').format.font = { name: 'Arial', size: 16, bold: true };
summary.getRange('A4:B4').values = [['Result', 'Rows']];
const statuses = Object.entries(v.row_reconciliation);
summary.getRangeByIndexes(4,0,statuses.length,2).values = statuses;
const totalRow = 5 + statuses.length;
summary.getRange(`A${totalRow}:B${totalRow}`).values = [['Total input rows', report.rows.length]];
summary.getRange(`A${totalRow+2}:B${totalRow+5}`).values = [
  ['Eligible rows',137],['Stored historical publications',v.stored_historical_publications],
  ['Unique imported DOIs',v.imported_unique_dois],['Faculty claimed total',v.faculty_claimed_total],
];
summary.getRange('D4:E4').values = [['Indexing (overlap possible)', 'Publications']];
const indexing = Object.entries(v.indexing_totals);
summary.getRangeByIndexes(4,3,indexing.length,2).values = indexing;
summary.getRange('G4:H4').values = [['Quartile', 'Publications']];
const quartiles = Object.entries(v.quartile_totals);
summary.getRangeByIndexes(4,6,quartiles.length,2).values = quartiles;
summary.getRange('D12:E14').values = [
  ['With student authors',v.with_student_authors],
  ['With multiple faculty authors',v.with_multiple_faculty_authors],
  ['Database integrity',v.integrity_check],
];
summary.getRange('A21:C21').values = [['Employee ID', 'Faculty name', 'Imported claimed publications']];
summary.getRangeByIndexes(21,0,v.claimant_summary.length,3).values = v.claimant_summary.map(r=>[r.employee_id,r.faculty_name,r.imported_claimed_publications]);
summary.getRange('A43').values = [['Archana Chittari — Excel row 86 — not imported']];
summary.getRange('A44').values = [['Indexing counts overlap where a publication has more than one index.']];
summary.getRange('A45').values = [['Claimant matching uses exact ORCID, canonical names and approved strong aliases.']];
summary.getRange('A46').values = [['Unmapped DOI authors remain UNKNOWN; no person or evidence records were created.']];
summary.getRange('A4:H46').format.font = {name:'Arial',size:11,color:'#202B3A'};
summary.getRange('A4:H46').format.rowHeight = 23;
summary.getRange('A4:H46').format.verticalAlignment = 'center';
summary.getRange('A:A').format.columnWidth = 47;
summary.getRange('B:B').format.columnWidth = 38;
summary.getRange('C:C').format.columnWidth = 29;
summary.getRange('D:D').format.columnWidth = 36;
summary.getRange('E:E').format.columnWidth = 17;
summary.getRange('F:F').format.columnWidth = 3;
summary.getRange('G:G').format.columnWidth = 15;
summary.getRange('H:H').format.columnWidth = 17;
summary.getRange('B5:B19').setNumberFormat('#,##0');
summary.getRange('C22:C40').setNumberFormat('#,##0');
function header(sheet, address) {
  sheet.getRange(address).format = {fill:'#253D5B',font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},
    horizontalAlignment:'center',verticalAlignment:'center',wrapText:true,rowHeight:38};
}
for (const range of ['A4:B4','D4:E4','G4:H4','A21:C21']) header(summary,range);
const keys = Object.keys(report.rows[0]);
const labels = ['Excel row','S.No','Normalized DOI','Excel title','Stored / DOI title','Excel claimant','Matched faculty','Employee ID',
  'Claimant in DOI authors','Excel journal','DOI journal','Publication date','Excel indexing','Excel impact factor','Excel quartile',
  'Stored indexing','Stored impact factor','Stored quartile','Publication ID','Import status','Warnings / errors'];
detail.getRange('A1').values = [['Source: F:\\Downloads\\Journals.xlsx — Journal. DOI metadata from Crossref; KPIs and claimant from Excel.']];
detail.getRangeByIndexes(2,0,1,labels.length).values = [labels];
const matrix = report.rows.map(r=>keys.map(k=>{
  if (k==='publication_date' && r[k]) return new Date(`${r[k]}T00:00:00Z`);
  if(Array.isArray(r[k])) return r[k].join(' | ');
  return r[k] ?? null;
}));
detail.getRangeByIndexes(3,0,matrix.length,keys.length).values = matrix;
detail.getRange('A3:U141').format.font = {name:'Arial',size:11,color:'#202B3A'};
detail.getRange('A3:U141').format.verticalAlignment = 'top';
detail.getRange('A3:U141').format.wrapText = true;
detail.getRange('A4:U141').format.rowHeight = 100;
detail.getRange('A:A').format.columnWidth = 10;
detail.getRange('B:B').format.columnWidth = 8;
detail.getRange('C:C').format.columnWidth = 48;
detail.getRange('D:E').format.columnWidth = 68;
detail.getRange('F:G').format.columnWidth = 35;
detail.getRange('H:H').format.columnWidth = 14;
detail.getRange('I:I').format.columnWidth = 17;
detail.getRange('J:K').format.columnWidth = 42;
detail.getRange('L:L').format.columnWidth = 17;
detail.getRange('M:R').format.columnWidth = 18;
detail.getRange('S:S').format.columnWidth = 16;
detail.getRange('T:T').format.columnWidth = 36;
detail.getRange('U:U').format.columnWidth = 75;
detail.getRange('L4:L141').setNumberFormat('yyyy-mm-dd');
detail.getRange('N4:N141').setNumberFormat('0.###');
detail.getRange('Q4:Q141').setNumberFormat('0.###');
header(detail,'A3:U3');
detail.tables.add('A3:U141',true,'JournalImportRows');
detail.getRange('A4:U141').format.autofitRows();
for (const column of ['A','B','L','O','R','S']) detail.getRange(`${column}4:${column}141`).format.horizontalAlignment = 'center';
detail.freezePanes.freezeRows(3);
detail.freezePanes.freezeColumns(2);
detail.getRange('T4:T141').conditionalFormats.add('notContainsText', {text:'IMPORTED',format:{fill:'#FFF0DE',font:{color:'#9C4A0A'}}});
workbook.recalculate();
await fs.mkdir(outputDir,{recursive:true});
console.log((await workbook.inspect({kind:'region',sheetId:'Summary',range:'A4:H19',maxChars:3500,tableMaxRows:16,tableMaxCols:8})).ndjson);
for (const [name, range, filename] of [['Summary','A1:H19','summary-preview.png'], ['Summary','A20:C40','claimants-preview.png'],
                                     ['Import rows','A1:I7','rows-preview.png'],['Import rows','L3:U7','status-preview.png']]) {
  const blob = await workbook.render({sheetName:name,range,scale:1,format:'png'});
  await fs.writeFile(`${outputDir}/${filename}`,new Uint8Array(await blob.arrayBuffer()));
}
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(`${outputDir}/journal-import.xlsx`);
console.log(`Saved ${outputDir}/journal-import.xlsx`);
