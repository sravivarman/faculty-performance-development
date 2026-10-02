"use client";
import {useEffect, useRef, useState} from "react";
import Link from "next/link";
import PublicationEditor, {DOIInput} from "@/components/PublicationEditor";
import PublicationImportQueue, {ImportRow} from "@/components/PublicationImportQueue";
import {api, ApiError, blankPublication, Masters, Publication} from "@/lib/api";
import {prepareQueuePublication} from "@/lib/publication-readiness";

type ParsedEntry = {entry_number:number;status:string;errors:string[];warnings:string[];duplicate_ids:number[];duplicate_entry?:number;publication?:Publication;differences:{field:string;bibtex:unknown;doi:unknown}[]};
export default function PublicationEntry() {
  const [method,setMethod]=useState<"DOI"|"BibTeX"|"Manual">("DOI");
  const [content,setContent]=useState("");
  const [bibtex,setBibtex]=useState("");
  const [enrich,setEnrich]=useState(true);
  const [rows,setRows]=useState<ImportRow[]>([]);
  const [masters,setMasters]=useState<Masters>();
  const [busy,setBusy]=useState(false);
  const [progress,setProgress]=useState("");
  const [error,setError]=useState("");
  const nextKey=useRef(1);
  useEffect(()=>{api<Masters>("/masters").then(setMasters).catch(e=>setError(e.message));},[]);
  function publication(metadata:Publication) {
    return prepareQueuePublication({...blankPublication(),...metadata,publication_date:metadata.publication_date || ""});
  }
  async function fetchSources() {
    setBusy(true);setError("");
    try {
      if(method==="BibTeX") {
        setProgress("Parsing and matching BibTeX…");
        const result=await api<{entries:ParsedEntry[]}>("/publications/parse-bibtex",{method:"POST",body:JSON.stringify({content:bibtex,enrich_doi:enrich})});
        const seen=new Set(rows.flatMap(row=>row.publication?.doi?[row.publication.doi]:[]));
        const added:ImportRow[]=[];
        for(const entry of result.entries) {
          const p=entry.publication?publication(entry.publication):undefined;
          if(p?.doi && seen.has(p.doi)) continue;
          if(p?.doi)seen.add(p.doi);
          added.push({key:nextKey.current++,source:p?.doi || `BibTeX entry ${entry.entry_number}`,publication:entry.errors.length?undefined:p,
            status:entry.errors.length?"INVALID":p?.doi && entry.duplicate_ids.length?"DUPLICATE":undefined,
            existingId:p?.doi?entry.duplicate_ids[0]:undefined,possibleDuplicates:!p?.doi?entry.duplicate_ids:undefined,
            error:entry.errors.join(" ") || undefined,warnings:entry.warnings,differences:entry.differences});
        }
        setRows(previous=>[...previous,...added]);setProgress(`${added.length} BibTeX entries added to queue.`);
      } else {
        const parsed=await api<{entries:DOIInput[]}>("/publications/parse-dois",{method:"POST",body:JSON.stringify({content})});
        const known=new Set(rows.map(row=>row.publication?.doi || row.source));
        const entries=parsed.entries.filter(entry=>!known.has(entry.doi || entry.source));
        for(let i=0;i<entries.length;i++) {
          const input=entries[i];setProgress(`Retrieving metadata: ${i} of ${entries.length} processed`);
          const key=nextKey.current++;let row:ImportRow={key,source:input.doi || input.source,status:"INVALID",error:input.error};
          if(input.doi) {
            try {row={key,source:input.doi,publication:publication({...await api<Publication>(`/publications/lookup-doi?doi=${encodeURIComponent(input.doi)}`),source_type:"DOI"})};}
            catch(e) {const failure=e as ApiError;row={...row,status:failure.detail?.publication_id?"DUPLICATE":failure.status===422?"INVALID":"FETCH_FAILED",error:failure.message,existingId:failure.detail?.publication_id};
              if(row.existingId)try{row.publication=await api<Publication>(`/publications/${row.existingId}`);}catch{/* Duplicate remains linked. */}
            }
          }
          setRows(previous=>[...previous,row]);
        }
        setProgress(`Metadata retrieval complete: ${entries.length} of ${entries.length} processed`);
      }
    } catch(e) {setError((e as Error).message);} finally {setBusy(false);}
  }
  return <><div className="page-heading"><div><div className="eyebrow">Research records</div><h1>Add Publication</h1><p className="muted">Add sources, match authors, set claimant and KPI fields, then add all ready publications.</p></div><Link href="/publications">← Publication overview</Link></div>
    <section className="panel" aria-label="Entry method"><h2>Add sources</h2><div className="actions">{(["DOI","BibTeX","Manual"] as const).map(value=><button key={value} type="button" aria-pressed={method===value} className={method===value?"":"secondary"} disabled={busy} onClick={()=>setMethod(value)}>{value}</button>)}</div>
      {method==="DOI" && <><label className="field">DOI or DOI link<textarea rows={4} value={content} onChange={e=>setContent(e.target.value)} placeholder="One DOI per line, comma or semicolon"/></label><div className="actions"><button disabled={busy || !content.trim()} onClick={fetchSources}>{busy?"Retrieving…":"Fetch metadata"}</button><button className="secondary" onClick={()=>setMethod("Manual")}>Enter manually</button></div></>}
      {method==="BibTeX" && <><label className="field">BibTeX content<textarea rows={6} value={bibtex} onChange={e=>setBibtex(e.target.value)}/></label><div className="actions"><button disabled={busy || !bibtex.trim()} onClick={fetchSources}>{busy?"Parsing…":"Parse BibTeX"}</button><label className="check"><input type="checkbox" checked={enrich} onChange={e=>setEnrich(e.target.checked)}/>Enrich missing fields using DOI metadata</label></div></>}
      {method!=="Manual" && <p className="muted">Sources append to the same queue. Nothing is saved during metadata lookup. Single and multiple entries use the same controls.</p>}
      {progress && <p role="status">{progress}</p>}{error && <div className="error" role="alert">{error}</div>}
    </section>
    <div hidden={method!=="Manual"}><PublicationEditor compact entryMethod="Manual"/></div>
    <div hidden={method==="Manual"}><PublicationImportQueue rows={rows} setRows={setRows} masters={masters} fetching={busy}/></div>
  </>;
}
