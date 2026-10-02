"use client";
import {useState} from "react";
import Link from "next/link";
import PublicationEditor, {PendingFile} from "@/components/PublicationEditor";
import {api, ApiError, INDEXING, label, Masters, Publication} from "@/lib/api";
import {CLASSIFICATIONS, isSaveable, QUARTILES, queueReadiness, queueWarnings} from "@/lib/publication-readiness";

export type ImportRow = {key:number;source:string;publication?:Publication;status?:string;error?:string;warnings?:string[];existingId?:number;possibleDuplicates?:number[];files?:PendingFile[];differences?:{field:string;bibtex:unknown;doi:unknown}[]};
export function rowStatus(row:ImportRow) {
  if(row.status==="DUPLICATE") return "DUPLICATE";
  if(!row.publication) return row.status || "FETCH_FAILED";
  if(!row.publication.id && row.possibleDuplicates?.length && !row.publication.duplicate_acknowledged) return "INVALID";
  return queueReadiness(row.publication);
}

export default function PublicationImportQueue({rows,setRows,masters,fetching}:{rows:ImportRow[];setRows:React.Dispatch<React.SetStateAction<ImportRow[]>>;masters?:Masters;fetching:boolean}) {
  const [selected,setSelected]=useState<number[]>([]);
  const [filter,setFilter]=useState("ALL");
  const [indexFilter,setIndexFilter]=useState("");
  const [classFilter,setClassFilter]=useState("");
  const [editing,setEditing]=useState<number>();
  const [saving,setSaving]=useState(false);
  const [notice,setNotice]=useState("");
  const [bulkIndex,setBulkIndex]=useState("SCOPUS");
  const [bulkClassification,setBulkClassification]=useState("UNKNOWN");
  const [bulkQuartile,setBulkQuartile]=useState("UNKNOWN");
  const [bulkImpact,setBulkImpact]=useState("");
  function update(key:number,values:Partial<Publication>) {
    setRows(previous=>previous.map(row=>row.key===key && row.publication?{...row,publication:{...row.publication,...values},error:undefined}:row));
  }
  function indexing(current:string[],value:string) {
    return ["NONE","UNKNOWN"].includes(value)?[value]:[...new Set([...current.filter(v=>!["NONE","UNKNOWN"].includes(v)),value])];
  }
  function bulk(values:Partial<Publication>,addIndex=false) {
    setRows(previous=>previous.map(row=>selected.includes(row.key) && row.publication && !row.publication.id && row.status!=="DUPLICATE"?
      {...row,publication:{...row.publication,...values,...(addIndex?{indexing:indexing(row.publication.indexing,bulkIndex)}:{})},error:undefined}:row));
  }
  async function uploadEvidence(row:ImportRow,publication:Publication) {
    let files=row.files || [];
    for(const queued of files) {
      const body=new FormData();body.append("file",queued.file);body.append("evidence_type",queued.type);
      await api(`/publications/${publication.id}/evidence`,{method:"POST",body});
      files=files.slice(1);
      setRows(previous=>previous.map(value=>value.key===row.key?{...value,files}:value));
    }
  }
  async function save(targets:ImportRow[]) {
    setSaving(true);setNotice("");let saved=0,failed=0;
    for(const row of targets) {
      if(!row.publication || !isSaveable(rowStatus(row))) continue;
      try {
        const publication=await api<Publication>("/publications",{method:"POST",body:JSON.stringify({...row.publication,academic_year_id:undefined})});
        saved++;
        setRows(previous=>previous.map(value=>value.key===row.key?{...value,publication,error:undefined}:value));
        await uploadEvidence(row,publication);
      } catch(e) {
        failed++;const error=e as ApiError;
        setRows(previous=>previous.map(value=>value.key===row.key?{...value,error:error.message,
          ...(error.detail?.publication_id?{status:"DUPLICATE",existingId:error.detail.publication_id}:{}),
          ...(error.detail?.possible_duplicate_ids?{possibleDuplicates:error.detail.possible_duplicate_ids}: {})}:value));
      }
    }
    setSaving(false);setNotice(`${saved} publication(s) added.${failed?` ${failed} operation(s) need attention; other ready records were processed.`:""}`);
  }
  const ready=rows.filter(row=>isSaveable(rowStatus(row)));
  const filtered=rows.filter(row=>{
    const p=row.publication,status=rowStatus(row);
    return (filter==="ALL" || filter==="READY" && isSaveable(status) || filter==="UNKNOWN_AUTHORS" && p?.authors.some(a=>a.person_type==="UNKNOWN") || filter===status || filter===p?.publication_type)
      && (!indexFilter || p?.indexing.includes(indexFilter)) && (!classFilter || p?.classification===classFilter);
  });
  const editable=rows.filter(row=>row.publication && !row.publication.id && row.status!=="DUPLICATE");
  const current=rows.find(row=>row.key===editing);
  return <section aria-label="Publication import queue">
    <div className="panel"><div className="row-between"><h2>Import queue</h2><button disabled={fetching || saving || !ready.length} onClick={()=>save(ready)}>{saving?"Adding…":`Add All Ready (${ready.length})`}</button></div>
      <p role="status">{rows.length} Found · {ready.length} Ready · {rows.filter(row=>rowStatus(row)==="NEEDS_CLAIMANT").length} Need Claimant · {rows.filter(row=>rowStatus(row)==="DUPLICATE").length} Duplicate · {rows.filter(row=>rowStatus(row)==="SAVED").length} Saved</p>
      <p className="muted">{rows.filter(row=>row.publication?.publication_type==="JOURNAL").length} Journal · {rows.filter(row=>row.publication?.publication_type==="CONFERENCE").length} Conference. Edit exceptions; UNKNOWN co-authors do not block adding a record.</p>
      <div className="actions"><label className="field">Filter queue<select value={filter} onChange={e=>setFilter(e.target.value)}>{["ALL","JOURNAL","CONFERENCE","READY","NEEDS_CLAIMANT","DUPLICATE","UNKNOWN_AUTHORS","SAVED"].map(v=><option key={v} value={v}>{label(v)}</option>)}</select></label><label className="field">Filter indexing<select value={indexFilter} onChange={e=>setIndexFilter(e.target.value)}><option value="">All indexing</option>{INDEXING.map(v=><option key={v} value={v}>{label(v)}</option>)}</select></label><label className="field">Filter classification<select value={classFilter} onChange={e=>setClassFilter(e.target.value)}><option value="">All classifications</option>{CLASSIFICATIONS.map(v=><option key={v} value={v}>{label(v)}</option>)}</select></label></div>
      <details><summary>Bulk edit selected rows · {selected.filter(key=>editable.some(row=>row.key===key)).length} selected</summary><div className="queue-bulk" inert={saving || undefined}>
        <label className="field">Bulk indexing<select value={bulkIndex} onChange={e=>setBulkIndex(e.target.value)}>{INDEXING.map(v=><option key={v} value={v}>{label(v)}</option>)}</select></label><button className="secondary small" disabled={!selected.length} onClick={()=>bulk({},true)}>Add indexing to selected</button>
        <label className="field">Bulk classification<select value={bulkClassification} onChange={e=>setBulkClassification(e.target.value)}>{CLASSIFICATIONS.map(v=><option key={v} value={v}>{label(v)}</option>)}</select></label><button className="secondary small" disabled={!selected.length} onClick={()=>bulk({classification:bulkClassification})}>Set classification for selected</button>
        <label className="field">Bulk quartile<select value={bulkQuartile} onChange={e=>setBulkQuartile(e.target.value)}>{QUARTILES.map(v=><option key={v} value={v}>{label(v)}</option>)}</select></label><button className="secondary small" disabled={!selected.length} onClick={()=>bulk({quartile:bulkQuartile})}>Set quartile for selected</button>
        <label className="field">Bulk impact factor<input type="number" min="0" step="any" value={bulkImpact} onChange={e=>setBulkImpact(e.target.value)}/></label><button className="secondary small" disabled={!selected.length || (bulkImpact!=="" && (!Number.isFinite(Number(bulkImpact)) || Number(bulkImpact)<0))} onClick={()=>bulk({impact_factor:bulkImpact===""?null:Number(bulkImpact)})}>Set impact factor for selected</button>
      </div></details>
    </div>
    {notice && <div className="notice" role="status">{notice}</div>}
    <div className="panel table-wrap import-queue" inert={saving || undefined}><table><thead><tr><th><input type="checkbox" aria-label="Select all editable rows" checked={editable.length>0 && editable.every(row=>selected.includes(row.key))} onChange={e=>setSelected(e.target.checked?editable.map(row=>row.key):[])}/></th>{["Status","Publication Type","Title","DOI","Journal / Conference","Publication Date","Matched Faculty","Claiming Faculty","Unknown Authors","Indexing","Classification","Impact Factor","Quartile","Action"].map(title=><th key={title}>{title}</th>)}</tr></thead><tbody>{filtered.map(row=>{
      const p=row.publication,status=rowStatus(row),locked=Boolean(p?.id || row.status==="DUPLICATE");
      const faculty=p?.authors.filter(a=>a.person_type==="FACULTY" && a.faculty_id) || [];
      const warnings=[...(row.warnings || []),...(p?queueWarnings(p):[])];
      return <tr key={row.key} data-status={status} aria-label={p?.title || row.source}>
        <td><input type="checkbox" aria-label={`Select ${p?.title || row.source}`} disabled={locked || !p} checked={selected.includes(row.key)} onChange={e=>setSelected(previous=>e.target.checked?[...previous,row.key]:previous.filter(key=>key!==row.key))}/></td>
        <td><span className="badge">{status}</span>{row.error && <p className="error" role="alert">{row.error}</p>}{!!warnings.length && <details><summary>{warnings.length} warnings</summary>{warnings.map((warning,i)=><p key={i}>{warning}</p>)}</details>}</td>
        <td>{p?<select aria-label="Publication type" value={p.publication_type} disabled={locked} onChange={e=>update(row.key,{publication_type:e.target.value})}>{p.publication_type==="OTHER" && <option value="OTHER">Choose type</option>}{["JOURNAL","CONFERENCE"].map(v=><option key={v} value={v}>{label(v)}</option>)}</select>:"—"}</td>
        <td className="queue-title">{p?.title || row.source}</td><td>{p?.doi || (p?"No DOI":row.source)}</td><td>{p?.journal_conference_name || p?.proceedings_title || p?.conference_name || "—"}</td>
        <td>{p?<input aria-label="Publication date" type="date" value={p.publication_date || ""} disabled={locked} onChange={e=>update(row.key,{publication_date:e.target.value})}/>:"—"}</td>
        <td>{faculty.map(a=>masters?.faculty.find(f=>f.id===a.faculty_id)?.name || a.author_name_from_source).join("; ") || "None matched"}</td>
        <td>{p?<select aria-label="Claiming faculty" disabled={locked} value={p.authors.find(a=>a.is_claiming_faculty)?.faculty_id || ""} onChange={e=>update(row.key,{authors:p.authors.map(a=>({...a,is_claiming_faculty:a.person_type==="FACULTY" && a.faculty_id===Number(e.target.value)}))})}><option value="">Select claimant</option>{faculty.map(a=><option key={a.author_order} value={a.faculty_id!}>{masters?.faculty.find(f=>f.id===a.faculty_id)?.name || a.author_name_from_source}</option>)}</select>:"—"}</td>
        <td>{p?.authors.filter(a=>a.person_type==="UNKNOWN").length ?? "—"}</td>
        <td>{p?<details><summary>{p.indexing.map(label).join(", ") || "Set indexing"}</summary>{INDEXING.map(v=><label className="check" key={v}><input type="checkbox" disabled={locked} checked={p.indexing.includes(v)} onChange={e=>update(row.key,{indexing:e.target.checked?indexing(p.indexing,v):p.indexing.filter(value=>value!==v)})}/>{label(v)}</label>)}</details>:"—"}</td>
        <td>{p?<select aria-label="Classification" disabled={locked} value={p.classification || "UNKNOWN"} onChange={e=>update(row.key,{classification:e.target.value})}>{CLASSIFICATIONS.map(v=><option key={v} value={v}>{label(v)}</option>)}</select>:"—"}</td>
        <td>{p?<input aria-label="Impact factor" disabled={locked} type="number" min="0" step="any" value={p.impact_factor ?? ""} onChange={e=>update(row.key,{impact_factor:e.target.value===""?null:Number(e.target.value)})}/>:"—"}</td>
        <td>{p?<select aria-label="Quartile" disabled={locked} value={p.quartile || "UNKNOWN"} onChange={e=>update(row.key,{quartile:e.target.value})}>{QUARTILES.map(v=><option key={v} value={v}>{label(v)}</option>)}</select>:"—"}</td>
        <td>{(row.existingId || p?.id)?<Link href={`/publications/${row.existingId || p?.id}`}>Open {row.existingId?"existing":"saved"}</Link>:<>{p && <><button className="secondary small" onClick={()=>setEditing(row.key)}>Edit</button><button className="small" disabled={!isSaveable(status)} onClick={()=>save([row])}>Add</button></>}<button className="danger small" onClick={()=>setRows(previous=>previous.filter(value=>value.key!==row.key))}>Remove</button></>}
          {!!row.possibleDuplicates?.length && !p?.id && <label className="check"><input type="checkbox" checked={Boolean(p?.duplicate_acknowledged)} onChange={e=>update(row.key,{duplicate_acknowledged:e.target.checked})}/>I checked the possible duplicates: {row.possibleDuplicates.map(id=><Link key={id} href={`/publications/${id}`} target="_blank">#{id} </Link>)}</label>}
          {p?.id && !!row.files?.length && <button className="secondary small" onClick={async()=>{setSaving(true);try {await uploadEvidence(row,p);setRows(previous=>previous.map(value=>value.key===row.key?{...value,error:undefined}:value));}catch(e){setNotice((e as Error).message);}finally{setSaving(false);}}}>Retry evidence upload</button>}
        </td>
      </tr>;
    })}</tbody></table>{!rows.length && <p className="empty">Add DOI or BibTeX sources to start the queue.</p>}</div>
    {current?.publication && <div className="queue-editor panel" role="dialog" aria-label="Edit queued publication"><div className="row-between"><h2>Edit exception · {current.publication.title}</h2><button className="secondary" onClick={()=>setEditing(undefined)}>Cancel editing</button></div><PublicationEditor key={current.key} compact preview={current.publication} queuedFiles={current.files} differences={current.differences} onApply={(publication,files)=>{setRows(previous=>previous.map(row=>row.key===current.key?{...row,publication,files,error:undefined}:row));setEditing(undefined);}}/></div>}
  </section>;
}
