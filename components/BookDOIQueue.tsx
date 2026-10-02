"use client";
import {useEffect,useRef,useState} from 'react';
import Link from 'next/link';
import {api,ApiError,label,Masters} from '@/lib/api';
import {blankBook,blankContributor,Book,BookMetadata} from '@/lib/books';
import {BookQueueItem,QueueStatus,readyItems,queueSummary} from '@/lib/book-queue';
import BookEditor from './BookEditor';
import type {PendingEvidence} from './EvidenceQueue';

type Row=BookQueueItem&{files:PendingEvidence[]};
type Validation={doi:string|null;status:QueueStatus;errors:string[];draft?:Book;existing?:Book};
type Parsed={source:string;doi:string|null;status:QueueStatus;error?:string};
export default function BookDOIQueue({onBusy}:{onBusy:(busy:boolean)=>void}){
  const [input,setInput]=useState('');const [rows,setRows]=useState<Row[]>([]);const live=useRef<Row[]>([]);
  const [busy,setBusy]=useState(false);const [notice,setNotice]=useState('');const [progress,setProgress]=useState('');
  const [filter,setFilter]=useState('All');const [editing,setEditing]=useState<number>();const [doiEditing,setDoiEditing]=useState<number>();
  const [masters,setMasters]=useState<Masters>();const [masterError,setMasterError]=useState('');
  const nextKey=useRef(1);const versions=useRef(new Map<number,number>());const controller=useRef<AbortController|null>(null);
  useEffect(()=>{api<Masters>('/masters').then(setMasters).catch(e=>setMasterError(e.message));return()=>controller.current?.abort();},[]);
  useEffect(()=>{onBusy(busy);},[busy,onBusy]);
  useEffect(()=>{if(editing!==undefined)document.getElementById('book-queue-review')?.scrollIntoView({behavior:'smooth',block:'start'});},[editing]);
  function commit(values:Row[]){live.current=values;setRows(values);}
  function change(key:number,values:Partial<Row>){commit(live.current.map(r=>r.key===key?{...r,...values}:r));}
  async function validate(row:Row){
    const revision=(versions.current.get(row.key)||0)+1;versions.current.set(row.key,revision);
    change(row.key,{validating:true,status:'NEEDS_REVIEW',selected:false});
    try{
      const result=await api<Validation>('/book-preview-validation',{method:'POST',body:JSON.stringify({draft:row.draft,type_resolved:row.typeResolved})});
      if(versions.current.get(row.key)!==revision)return;
      const doi=result.doi;
      const repeated=doi&&live.current.find(r=>r.key!==row.key&&r.doi===doi);
      if(result.status==='READY'&&repeated){change(row.key,{doi,status:'DUPLICATE',errors:['This normalized DOI is already in this queue.'],existingId:repeated.draft.id,validating:false});return;}
      change(row.key,{...result,doi:result.doi,existingId:result.existing?.id,validating:false});
    }catch(e){if(versions.current.get(row.key)===revision)change(row.key,{status:'NEEDS_REVIEW',errors:[`Validation could not be completed. Review and retry. ${(e as Error).message}`],validating:false});}
  }
  async function duplicate(key:number,id:number,message:string){
    change(key,{status:'DUPLICATE',existingId:id,errors:[message],selected:false});
    try{change(key,{existing:await api<Book>(`/books/${id}`)});}catch{/* The existing link remains usable if detail fetch fails. */}
  }
  async function retrieve(row:Row,signal:AbortSignal){
    if(!row.doi||signal.aborted)return;
    change(row.key,{status:'FETCHING',errors:[],selected:false});
    try{
      const metadata=await api<BookMetadata>(`/book-metadata?doi=${encodeURIComponent(row.doi)}`,{signal});
      if(signal.aborted)return;
      const {warnings,source_type,contributors,...values}=metadata;
      const draft:Book={...blankBook(),...values,title:metadata.title||'',publisher:metadata.publisher||'',publication_date:metadata.publication_date||'',contributors:(contributors||[]).map((c,n)=>({...blankContributor(n+1),...c}))};
      const updated={...row,draft,doi:draft.doi,typeResolved:!!metadata.work_type,retrieved:true,errors:warnings||[],status:'NEEDS_REVIEW' as const};
      change(row.key,updated);await validate(updated);
    }catch(e){if(signal.aborted)return;const error=e as ApiError;
      if(error.detail?.book_id)await duplicate(row.key,error.detail.book_id,error.message);
      else change(row.key,{status:error.status===422?'NEEDS_REVIEW':'LOOKUP_FAILED',errors:[error.message]});
    }
  }
  async function fetchBatch(){
    setBusy(true);setNotice('');const abort=new AbortController();controller.current=abort;
    try{
      const parsed=await api<{entries:Parsed[]}>('/publications/parse-dois',{method:'POST',body:JSON.stringify({content:input}),signal:abort.signal});
      const incoming:Row[]=[];
      for(const item of parsed.entries){
        if(live.current.some(r=>item.doi?r.doi===item.doi:r.source.toLowerCase()===item.source.toLowerCase()))continue;
        incoming.push({key:nextKey.current++,source:item.source,doi:item.doi,status:item.doi?'PENDING':'INVALID_DOI',draft:{...blankBook(),doi:item.doi||item.source},typeResolved:false,retrieved:false,selected:false,errors:item.error?[item.error]:[],files:[]});
      }
      commit([...live.current,...incoming]);
      for(let index=0;index<incoming.length;index++){
        if(abort.signal.aborted)return;
        setProgress(`Fetching ${index+1} of ${incoming.length}`);await retrieve(incoming[index],abort.signal);
      }
      setNotice(`${incoming.length} new unique item(s) processed. Previously queued items retained. Nothing has been saved.`);
    }catch(e){if(!abort.signal.aborted)setNotice((e as Error).message);}
    finally{if(!abort.signal.aborted){setBusy(false);setProgress('');}}
  }
  async function retry(row:Row){
    setBusy(true);const abort=new AbortController();controller.current=abort;
    try{
      const parsed=await api<{entries:Parsed[]}>('/publications/parse-dois',{method:'POST',body:JSON.stringify({content:row.source})});
      if(parsed.entries.length!==1||!parsed.entries[0].doi){change(row.key,{status:'INVALID_DOI',errors:['Enter exactly one valid DOI for this item.']});return;}
      const doi=parsed.entries[0].doi;
      if(live.current.some(r=>r.key!==row.key&&r.doi===doi)){change(row.key,{status:'DUPLICATE',errors:['This DOI is already in the queue.']});return;}
      const updated={...row,doi,draft:{...blankBook(),doi},typeResolved:false,retrieved:false};change(row.key,updated);setDoiEditing(undefined);await retrieve(updated,abort.signal);
    }catch(e){change(row.key,{status:'LOOKUP_FAILED',errors:[(e as Error).message]});}finally{setBusy(false);}
  }
  async function uploadEvidence(row:Row,id:number){
    let remaining=[...row.files];
    for(const file of row.files){
      const form=new FormData();form.append('file',file.file);form.append('evidence_type',file.type);
      await api(`/books/${id}/evidence`,{method:'POST',body:form});remaining=remaining.slice(1);change(row.key,{files:remaining});
    }
  }
  async function save(items:Row[]){
    setBusy(true);setNotice('');let saved=0,failed=0;
    for(const item of items){
      const row=live.current.find(r=>r.key===item.key);
      if(!row||row.status!=='READY'||row.draft.id||row.validating)continue;
      try{
        // One ordinary transactional book save per item. A failure never cancels later rows.
        const record=await api<Book>('/books',{method:'POST',body:JSON.stringify(row.draft)});
        change(row.key,{draft:record,status:'SAVED',selected:false,errors:[]});saved++;
        try{await uploadEvidence(row,record.id!);}catch(e){change(row.key,{errors:[`Record saved. Evidence upload incomplete: ${(e as Error).message}`]});}
      }catch(e){const error=e as ApiError;failed++;
        if(error.detail?.book_id)await duplicate(row.key,error.detail.book_id,error.message);
        else change(row.key,{status:'NEEDS_REVIEW',selected:false,errors:[error.message]});
      }
    }
    setBusy(false);setNotice(`${saved} Book / Chapter record(s) saved. ${failed} save(s) need attention. Other exception items remain in the queue.`);
  }
  const ready=readyItems(rows) as Row[];const active=rows.find(r=>r.key===editing);
  const visible=rows.filter(r=>filter==='All'||(filter==='Failed'?['LOOKUP_FAILED','INVALID_DOI'].includes(r.status):r.status===filter));
  function facultyAuthors(row:Row){return (row.existing||row.draft).contributors.filter(c=>c.role==='AUTHOR'&&c.person_type==='FACULTY'&&c.faculty_id&&c.institution_scope==='CURRENT_DEPARTMENT'&&masters?.faculty.some(f=>f.id===c.faculty_id&&f.is_active));}
  function name(id:number){return masters?.faculty.find(f=>f.id===id)?.name||`Faculty #${id}`;}
  return <div className="book-doi-queue"><section className="panel"><h2>Enter DOI</h2><label className="field" htmlFor="book-doi-input">DOI lookup<textarea id="book-doi-input" aria-label="DOI lookup" rows={4} disabled={busy} value={input} onChange={e=>setInput(e.target.value)} placeholder="One or many DOIs, separated by lines, commas, semicolons or identifiable DOI prefixes"/></label><button disabled={busy||!input.trim()} onClick={fetchBatch}>{busy&&progress?'Fetching…':'Fetch Metadata'}</button><p className="muted">Duplicates are removed after normalization. Metadata retrieval is sequential. Nothing is saved until you choose a save action.</p>{progress&&<p role="status">{progress}</p>}{notice&&<p role="status" className="notice">{notice}</p>}</section>
    {masterError&&<p className="error" role="alert">Faculty Master could not be loaded: {masterError} <button className="secondary" onClick={()=>api<Masters>('/masters').then(m=>{setMasters(m);setMasterError('');}).catch(e=>setMasterError(e.message))}>Retry Master List</button></p>}
    {!!rows.length&&<><section className="panel"><div className="row-between"><h2>DOI Import Queue</h2><label className="field">Queue filter<select value={filter} onChange={e=>setFilter(e.target.value)}>{['All','READY','NEEDS_REVIEW','NEEDS_CLAIMANT','DUPLICATE','Failed','SAVED'].map(v=><option key={v} value={v}>{v==='All'||v==='Failed'?v:label(v)}</option>)}</select></label></div><div className="actions"><button disabled={busy||!!active||!ready.length} onClick={()=>save(ready)}>Add All Ready ({ready.length})</button><button disabled={busy||!!active||!ready.length} className="secondary" onClick={()=>commit(live.current.map(r=>({...r,selected:r.status==='READY'&&!r.validating&&!r.draft.id})))}>Select All Ready</button><button disabled={busy||!!active||!ready.some(r=>r.selected)} onClick={()=>save(ready.filter(r=>r.selected))}>Save Selected ({ready.filter(r=>r.selected).length})</button><button disabled={busy} className="secondary" onClick={()=>commit(live.current.map(r=>({...r,selected:false})))}>Clear Selection</button></div>
      <div className="table-wrap"><table><thead><tr>{['Select','Status','Type','Title','Book / Container Title','DOI','Publisher','Publication Date','Matched Faculty','Claiming Faculty','ISBN','Classification','Action'].map(v=><th key={v}>{v}</th>)}</tr></thead><tbody>{visible.map(row=>{
        const work=row.existing||row.draft;const authors=facultyAuthors(row);const claim=work.contributors.find(c=>c.is_claiming_faculty);const locked=busy||!!active||['SAVED','DUPLICATE','FETCHING','PENDING'].includes(row.status);
        return <tr key={row.key} data-queue-key={row.key}><td><input type="checkbox" aria-label={`Select ${row.doi||row.source}`} checked={row.selected} disabled={locked||row.status!=='READY'||row.validating} onChange={e=>change(row.key,{selected:e.target.checked})}/></td><td><span className="badge">{row.validating?'Checking…':row.status}</span>{row.errors.map((error,i)=><small key={i}>{error}</small>)}</td><td>{row.existing||row.status==='SAVED'?label(work.work_type):<select aria-label={`Type for ${row.doi||row.source}`} disabled={locked||row.validating} value={row.typeResolved?work.work_type:''} onChange={e=>{const updated={...row,typeResolved:true,draft:{...row.draft,work_type:e.target.value as Book['work_type']}};change(row.key,updated);void validate(updated);}}><option value="" disabled>Select type</option><option value="BOOK">Book</option><option value="BOOK_CHAPTER">Book Chapter</option></select>}</td><td>{work.title||'—'}</td><td>{work.parent_book_title||'—'}</td><td>{doiEditing===row.key?<><input aria-label={`Edit DOI ${row.key}`} value={row.source} disabled={busy} onChange={e=>change(row.key,{source:e.target.value,doi:null,draft:{...row.draft,doi:e.target.value,metadata_source:null,metadata_fetched_at:null,raw_metadata_json:null},status:'INVALID_DOI',retrieved:false,typeResolved:false,selected:false,errors:['Fetch the corrected DOI to continue.']})}/><button disabled={busy} onClick={()=>retry(row)}>Fetch Corrected DOI</button></>:row.doi||row.source}</td><td>{work.publisher||'—'}</td><td>{work.publication_date||'—'}</td><td>{authors.map(c=>name(c.faculty_id!)).join(', ')||'None'}<small>{work.contributors.filter(c=>c.role==='AUTHOR'&&c.person_type==='FACULTY').length} Faculty · {work.contributors.filter(c=>c.role==='AUTHOR'&&c.person_type==='STUDENT').length} Student · {work.contributors.filter(c=>c.role==='AUTHOR'&&c.person_type==='UNKNOWN').length} Unknown</small></td><td>{row.existing||row.status==='SAVED'?(claim?.person_name||claim?.contributor_name||'—'):<select aria-label={`Claiming Faculty for ${row.doi||row.source}`} disabled={locked||row.validating||!authors.length} value={row.draft.contributors.find(c=>c.is_claiming_faculty)?.faculty_id||''} onChange={e=>{const id=Number(e.target.value);const updated={...row,draft:{...row.draft,contributors:row.draft.contributors.map(c=>({...c,is_claiming_faculty:c.role==='AUTHOR'&&c.faculty_id===id}))}};change(row.key,updated);void validate(updated);}}><option value="">Select Faculty</option>{authors.map(c=><option key={c.contributor_order} value={c.faculty_id!}>{name(c.faculty_id!)}</option>)}</select>}</td><td>{work.isbn||'—'}{work.eisbn&&<small>eISBN: {work.eisbn}</small>}</td><td>{locked?label(work.classification||'UNKNOWN'):<select aria-label={`Classification for ${row.doi||row.source}`} disabled={row.validating} value={work.classification||'UNKNOWN'} onChange={e=>{const updated={...row,draft:{...row.draft,classification:e.target.value as Book['classification']}};change(row.key,updated);void validate(updated);}}>{['INTERNATIONAL','NATIONAL','OTHER','UNKNOWN'].map(v=><option key={v} value={v}>{label(v)}</option>)}</select>}</td><td><div className="actions">{row.existingId&&<Link href={`/books/${row.existingId}`}>View Existing</Link>}{row.status==='SAVED'?<><Link href={`/books/${row.draft.id}`}>View Saved</Link>{!!row.files.length&&<button disabled={busy} onClick={async()=>{setBusy(true);try{await uploadEvidence(row,row.draft.id!);change(row.key,{errors:[]});}catch(e){change(row.key,{errors:[(e as Error).message]});}finally{setBusy(false);}}}>Retry Evidence</button>}</>:row.status!=='DUPLICATE'&&<><button disabled={locked||row.validating} className="secondary small" onClick={()=>setEditing(row.key)}>{row.status==='LOOKUP_FAILED'?'Enter Manually':'Review / Edit'}</button>{['LOOKUP_FAILED','INVALID_DOI','NEEDS_REVIEW'].includes(row.status)&&<button disabled={busy||!!active} className="secondary small" onClick={()=>{setDoiEditing(row.key);}}>Edit DOI</button>}{row.status==='LOOKUP_FAILED'&&<button disabled={busy||!!active} className="secondary small" onClick={()=>retry(row)}>Retry Lookup</button>}</>}{row.status!=='SAVED'&&<button className="danger small" disabled={busy||!!active||row.validating} onClick={()=>{versions.current.delete(row.key);commit(live.current.filter(r=>r.key!==row.key));}}>Remove</button>}</div></td></tr>;
      })}</tbody></table></div></section><section className="panel"><h2>Batch Summary</h2><dl className="detail-grid">{Object.entries(queueSummary(rows)).map(([key,value])=><div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl></section></>}
    {active&&<section id="book-queue-review" aria-label="Item review"><BookEditor key={active.key} initial={active.draft} initialFiles={active.files} hideLookup typeConfirmationRequired={!active.typeResolved} requireAuthorClaimant onCancel={()=>setEditing(undefined)} onReview={async(draft,files)=>{const updated={...active,draft,doi:draft.doi,source:draft.doi||active.source,files,typeResolved:true};change(active.key,updated);await validate(updated);setEditing(undefined);}}/></section>}
    <style>{`.book-doi-queue table{min-width:1450px}.book-doi-queue td{min-width:100px;vertical-align:top}.book-doi-queue td:first-child{min-width:56px}.book-doi-queue td small{display:block;max-width:240px;overflow-wrap:anywhere}.book-doi-queue .table-wrap select{min-width:145px;max-width:200px}.book-doi-queue .table-wrap .actions{flex-direction:row;flex-wrap:wrap;align-items:flex-start;gap:6px}.book-doi-queue .table-wrap .actions button{white-space:nowrap}.book-doi-queue .table-wrap td:last-child{min-width:240px}.book-doi-queue .table-wrap td:nth-child(4),.book-doi-queue .table-wrap td:nth-child(5){min-width:180px}.book-doi-queue .table-wrap td:nth-child(6){overflow-wrap:anywhere;max-width:220px}`}</style>
  </div>;
}
