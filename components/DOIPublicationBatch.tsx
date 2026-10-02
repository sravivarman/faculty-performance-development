"use client";
import {useEffect, useRef, useState} from "react";
import Link from "next/link";
import PublicationEditor, {DOIInput, PublicationEditorHandle} from "@/components/PublicationEditor";
import {api, ApiError, blankPublication, label, Publication} from "@/lib/api";

import {isSaveable} from "@/lib/publication-readiness";

type Row = DOIInput & {publication?:Publication;draft?:Publication;existing?:Publication;existingId?:number};

export default function DOIPublicationBatch({inputs,onBusyChange}:{inputs:DOIInput[];onBusyChange?:(busy:boolean)=>void}) {
  const [rows,setRows]=useState<Row[]>(inputs);
  const [completed,setCompleted]=useState(0);
  const [fetching,setFetching]=useState(true);
  const [saving,setSaving]=useState(false);
  const [notice,setNotice]=useState("");
  const editors=useRef<Record<number,PublicationEditorHandle|null>>({});
  useEffect(()=>{onBusyChange?.(fetching || saving);},[fetching,saving,onBusyChange]);
  useEffect(()=>{
    const controller=new AbortController();
    async function retrieve() {
      // One provider request at a time; errors belong to a row, never to the batch.
      for(let i=0;i<inputs.length;i++) {
        if(controller.signal.aborted) return;
        const input=inputs[i];
        let result:Partial<Row>={};
        if(input.doi) {
          setRows(previous=>previous.map((row,n)=>n===i?{...row,status:"FETCHING"}:row));
          try {
            const metadata=await api<Publication>(`/publications/lookup-doi?doi=${encodeURIComponent(input.doi)}`,{signal:controller.signal});
            const publication={...blankPublication(),...metadata,source_type:"DOI",authors:(metadata.authors || []).map(a=>({...a,is_claiming_faculty:false})),publication_date:metadata.publication_date || ""};
            result={publication,draft:publication,status:"AUTHOR_REVIEW"};
          } catch(e) {
            if(controller.signal.aborted) return;
            const error=e as ApiError;
            const existingId=error.detail?.publication_id;
            result={status:existingId?"DUPLICATE":error.status===422?"INVALID_DOI":"FETCH_FAILED",error:error.message,existingId};
            if(existingId) {
              try {result.existing=await api<Publication>(`/publications/${existingId}`,{signal:controller.signal});}
              catch { /* Keep the duplicate link even when its detail request fails. */ }
            }
          }
        }
        if(controller.signal.aborted) return;
        setRows(previous=>previous.map((row,n)=>n===i?{...row,...result}:row));
        setCompleted(i+1);
      }
      setFetching(false);
    }
    // Defer the first request so React's development effect replay can cancel
    // its discarded setup before it sends an extra provider request.
    void Promise.resolve().then(()=>{if(!controller.signal.aborted) return retrieve();});
    return ()=>controller.abort();
  },[inputs]);

  async function saveReady() {
    setSaving(true);setNotice("");
    let saved=0,failed=0;
    const ready=rows.flatMap((row,index)=>isSaveable(row.status)?[index]:[]);
    for(const index of ready) {
      try {if(await editors.current[index]?.saveReady()) saved++;else failed++;}
      catch {failed++;} // An individual save failure must not block later ready rows.
    }
    setSaving(false);
    setNotice(`${saved} publication(s) saved.${failed?` ${failed} could not be saved; review the affected records and retry.`:""} Other records remain available for review.`);
  }
  const readyCount=rows.filter(row=>isSaveable(row.status)).length;
  return <section aria-label="DOI batch preview">
    <div className="panel"><h2>Review DOI publications · {rows.length} entries</h2><p role="status">{fetching?`Retrieving metadata: ${completed} of ${rows.length} processed`:`Metadata retrieval complete: ${completed} of ${rows.length} processed`}</p><progress max={rows.length} value={completed} aria-label="DOI retrieval progress"/><p className="muted">Select a claimant and review authors and KPI fields for each publication. Unknown co-authors may remain unclassified and do not block saving. Dates that are incomplete need manual completion.</p><button type="button" disabled={fetching || saving || !readyCount} onClick={saveReady}>{saving?"Saving ready publications…":`Save Ready Publications · ${readyCount}`}</button> <span>{readyCount} READY</span></div>
    {notice && <div className="notice" role="status">{notice}</div>}
    <div inert={saving || undefined}>{rows.map((row,index)=>{
      const p=row.draft || row.existing;
      const faculty=p?.authors.filter(a=>a.person_type==="FACULTY") || [];
      const students=p?.authors.filter(a=>a.person_type==="STUDENT") || [];
      return <details className="panel doi-entry" key={index} open={rows.length===1}><summary><strong>{index+1}. {p?.title || row.doi || row.source}</strong> <span className="badge">{row.status}</span><div className="muted">{p?.doi || row.doi || row.source}</div></summary>
        <dl className="grid">
          <div><dt>DOI</dt><dd>{p?.doi || row.doi || row.source}</dd></div>
          <div><dt>Title</dt><dd>{p?.title || "Not available"}</dd></div>
          <div><dt>Publication Type</dt><dd>{p?label(p.publication_type):"Not available"}</dd></div>
          <div><dt>Journal / Conference</dt><dd>{p?.journal_conference_name || p?.proceedings_title || p?.conference_name || "Not supplied"}</dd></div>
          <div><dt>Publication Date</dt><dd>{p?.publication_date || "Needs completion"}</dd></div>
          <div><dt>Number of Authors</dt><dd>{p?.authors.length ?? "Not available"}</dd></div>
          <div><dt>Internal Faculty Authors</dt><dd>{faculty.map(a=>a.person_name || a.author_name_from_source).join("; ") || "None matched"}</dd></div>
          <div><dt>Confirmed Student Authors</dt><dd>{students.map(a=>a.person_name || a.author_name_from_source).join("; ") || "None matched"}</dd></div>
          <div><dt>Claiming Faculty</dt><dd>{faculty.find(a=>a.is_claiming_faculty)?.author_name_from_source || (p?.is_claimable===false?"Explicitly non-claimable":"Select for this publication")}</dd></div>
          <div><dt>Indexing</dt><dd>{p?.indexing.map(label).join(", ") || "Not supplied"}</dd></div>
          <div><dt>Impact Factor</dt><dd>{p?.impact_factor ?? "Not supplied"}</dd></div>
          <div><dt>Quartile</dt><dd>{p?.quartile || "Not supplied"}</dd></div>
          <div><dt>Status</dt><dd>{row.status}</dd></div>
        </dl>
        {row.error && <div className={row.status==="DUPLICATE"?"notice":"error"} role="alert">{row.error}</div>}
        {row.existingId && <Link href={`/publications/${row.existingId}`}>Open existing publication #{row.existingId}</Link>}
        {p?.id && !row.existingId && <Link href={`/publications/${p.id}`}>Open saved publication #{p.id}</Link>}
        {row.publication && <PublicationEditor compact batch preview={row.publication} ref={handle=>{editors.current[index]=handle;}} onPreviewChange={(draft,status)=>setRows(previous=>previous[index].draft===draft && previous[index].status===status?previous:previous.map((value,n)=>n===index?{...value,draft,status}:value))} onSaved={publication=>setRows(previous=>previous.map((value,n)=>n===index?{...value,draft:publication,status:"SAVED"}:value))}/>}
      </details>;
    })}</div>
  </section>;
}
