"use client";
import {useEffect,useState} from "react";
import Link from "next/link";
import {api,ApiError} from "@/lib/api";
import {Book,BookMetadata,blankContributor} from "@/lib/books";

export default function BookDOILookup({draft,onApply,onTypeReview,onBusy}:{draft:Book;onApply:(values:Partial<Book>)=>void;onTypeReview:(value:boolean)=>void;onBusy:(value:boolean)=>void}){
  const [mode,setMode]=useState(draft.id?"MANUAL":"DOI");const [doi,setDoi]=useState(draft.doi||"");
  const [busy,setBusy]=useState(false);const [message,setMessage]=useState("");const [warnings,setWarnings]=useState<string[]>([]);const [existing,setExisting]=useState<number>();
  useEffect(()=>{setDoi(draft.doi||"");},[draft.doi]);
  async function fetch(){setBusy(true);onBusy(true);setMessage("");setExisting(undefined);setWarnings([]);onApply({doi,metadata_source:null,metadata_fetched_at:null,raw_metadata_json:null});
    try{const metadata=await api<BookMetadata>(`/book-metadata?doi=${encodeURIComponent(doi)}`);
      const {source_type,warnings:notes,contributors,...values}=metadata;
      onApply({...values,contributors:(contributors||[]).map((c,n)=>({...blankContributor(n+1),...c}))});
      setDoi(metadata.doi||doi);setWarnings(notes||[]);onTypeReview(!!metadata.work_type);
      setMessage(`Metadata retrieved${source_type?` (${source_type})`:""}. Review the editable details, contributors and claimant below. Nothing has been saved.`);
    }catch(e){const error=e as ApiError;setExisting(error.detail?.book_id);setMessage(error.detail?.book_id?"A Book / Chapter with this DOI already exists.":`Metadata could not be retrieved for this DOI. You can continue with manual entry. ${error.message}`);}
    finally{setBusy(false);onBusy(false);}
  }
  return <section className="panel"><div className="actions" aria-label="Entry method"><button type="button" aria-pressed={mode==="DOI"} className={mode==="DOI"?"":"secondary"} onClick={()=>setMode("DOI")}>Add by DOI</button><button type="button" aria-pressed={mode==="MANUAL"} className={mode==="MANUAL"?"":"secondary"} onClick={()=>setMode("MANUAL")}>Manual Entry</button></div>{mode==="DOI"?<><h2>Enter DOI</h2><label className="field">DOI lookup<input disabled={busy} value={doi} placeholder="10.1234/book or https://doi.org/…" onChange={e=>{setDoi(e.target.value);setExisting(undefined);setMessage("");onApply({doi:e.target.value,metadata_source:null,metadata_fetched_at:null,raw_metadata_json:null});}}/></label><button type="button" disabled={busy||!doi.trim()} onClick={fetch}>{busy?"Fetching…":"Fetch Metadata"}</button><p className="muted">Fetch → Review → Select Claiming Faculty → Save. Fetching does not save a record.</p></>:<p className="muted">Complete the fields below. DOI and ISBN are optional and independent.</p>}{message&&<p className="notice" role="status">{message} {existing&&<Link href={`/books/${existing}`}>View Existing →</Link>}</p>}{warnings.map(w=><p className="notice" role="status" key={w}>{w}</p>)}</section>;
}
