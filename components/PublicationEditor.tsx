"use client";
import {FormEvent, Ref, useEffect, useImperativeHandle, useRef, useState} from "react";
import Link from "next/link";
import {useRouter} from "next/navigation";
import {api, ApiError, Author, blankAuthor, blankPublication, INDEXING, label, Masters, PersonType, Publication} from "@/lib/api";

import {authorWarnings, doiReadiness, isSaveable, CLASSIFICATIONS, QUARTILES} from "@/lib/publication-readiness";

const commonBibliography: [keyof Publication,string,string?][] = [
  ["title","Title"], ["doi","DOI"], ["publication_date","Publication date","date"],
  ["publisher","Publisher"],
  ["online_publication_date","Online publication date","date"], ["print_publication_date","Print publication date","date"],
  ["pages_or_article_number","Pages / Article number"], ["url","Publication URL","url"],
];
export type PendingFile = {file: File; type: string};
export type DOIInput = {source:string;doi:string|null;status:string;error?:string};
export type PublicationEditorHandle = {saveReady:()=>Promise<Publication|undefined>};
function differenceText(value:unknown) {return Array.isArray(value) ? (value as Author[]).map(a=>a.author_name_from_source).join("; ") : String(value);}
export default function PublicationEditor({initial,preview,entryMethod="DOI",compact=false,onSaved,onStatusChange,duplicateDoi,differences=[],onMultipleDois,batch=false,onPreviewChange,ref,onApply,queuedFiles=[]}: {initial?: Publication;preview?:Publication;entryMethod?:"DOI"|"Manual";compact?:boolean;onSaved?:(p:Publication)=>void;onStatusChange?:(s:string)=>void;duplicateDoi?:string|null;differences?:{field:string;bibtex:unknown;doi:unknown}[];onMultipleDois?:(entries:DOIInput[])=>void;batch?:boolean;onPreviewChange?:(p:Publication,status:string)=>void;ref?:Ref<PublicationEditorHandle>;onApply?:(p:Publication,files:PendingFile[])=>void;queuedFiles?:PendingFile[]}) {
  const router = useRouter();
  const [draft, setDraft] = useState<Publication>(initial || (preview ? {...blankPublication(),...preview,publication_date:preview.publication_date || ""} : blankPublication()));
  const isBibtex = Boolean(draft.raw_bibtex);
  const bibliography: [keyof Publication,string,string?][] = [...commonBibliography,...(draft.publication_type === "CONFERENCE" ? [
    ["conference_name","Conference name"], ["proceedings_title","Proceedings title"],
    ["conference_start_date","Conference start date","date"], ["conference_end_date","Conference end date","date"],
    ["conference_location","Conference location"], ["conference_organizer","Organizer"], ["isbn","ISBN"],
  ] : [["journal_conference_name","Journal name"], ["volume","Volume"], ["issue","Issue"], ["issn","ISSN"], ["eissn","eISSN"]]) as [keyof Publication,string,string?][]];
  const [masters, setMasters] = useState<Masters>();
  const [lookup, setLookup] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError>();
  const [notice, setNotice] = useState("");
  const [reviewed, setReviewed] = useState(Boolean(onApply));
  const [files, setFiles] = useState<PendingFile[]>(queuedFiles);
  const [fileType, setFileType] = useState("PUBLICATION_PROOF");
  const formRef = useRef<HTMLFormElement>(null);
  const [duplicateId,setDuplicateId] = useState<number>();
  useEffect(()=>{api<Masters>("/masters").then(setMasters).catch(setError);},[]);
  function patch(values: Partial<Publication>) {setDraft(d=>({...d,...values,duplicate_acknowledged:values.duplicate_acknowledged ?? false}));setReviewed(Boolean(onApply));}
  function authorList(authors: Author[]) {
    const faculty = authors.filter(a=>a.person_type === "FACULTY" && a.faculty_id);
    if(!isBibtex && !batch && draft.is_claimable && faculty.length === 1 && !authors.some(a=>a.is_claiming_faculty)) faculty[0].is_claiming_faculty = true;
    patch({authors});
  }
  function authorPatch(index: number, values: Partial<Author>) {authorList(draft.authors.map((a,i)=>i===index ? {...a,...values} : {...a}));}
  async function fetchDoi() {
    setBusy(true);setError(undefined);setNotice("");
    try {
      const parsed = await api<{entries:DOIInput[]}>("/publications/parse-dois",{method:"POST",body:JSON.stringify({content:lookup})});
      if(!parsed.entries.length) throw new ApiError("Enter at least one DOI.");
      if(parsed.entries.length > 1 && onMultipleDois) {onMultipleDois(parsed.entries);return;}
      const metadata = await api<Partial<Publication>>(`/publications/lookup-doi?doi=${encodeURIComponent(parsed.entries[0].doi || parsed.entries[0].source)}`);
      const authors = metadata.authors || [];
      const faculty = authors.filter(a=>a.person_type === "FACULTY");
      if(faculty.length === 1) faculty[0].is_claiming_faculty = true;
      setDraft({...blankPublication(),...metadata,source_type:"DOI",authors,publication_date:metadata.publication_date || ""});
      setReviewed(false);setNotice("Metadata fetched. Review the dates, identify authors and confirm institutional indexing before saving. Partial source dates need manual completion.");
    } catch(e) {setError(e as ApiError);}
    finally {setBusy(false);}
  }
  async function save(event?: FormEvent) {
    event?.preventDefault(); if(onApply) {onApply(draft,files);return draft;} if(!reviewed || busy || (!isSaveable(reviewStatus) && reviewStatus !== "SAVED")) return;
    setBusy(true);setError(undefined);setNotice("");
    let saved: Publication | undefined;
    let remaining = [...files];
    try {
      // Recompute academic year on the server when an edited date crosses years.
      const payload = {...draft, academic_year_id: undefined};
      saved = await api<Publication>(draft.id ? `/publications/${draft.id}` : "/publications", {method:draft.id ? "PUT" : "POST",body:JSON.stringify(payload)});
      setDraft(saved);
      for(const queued of files) {
        const data = new FormData();data.append("file",queued.file);data.append("evidence_type",queued.type);
        await api(`/publications/${saved.id}/evidence`,{method:"POST",body:data});
        remaining = remaining.slice(1);setFiles(remaining);
      }
      if(onSaved) {onSaved(saved);setNotice(`Publication ${saved.id} saved. Other entries remain available for review.`);}
      else router.push(`/publications/${saved.id}`);
    } catch(e) {
      setError(e as ApiError);
      if((e as ApiError).detail?.publication_id) setDuplicateId((e as ApiError).detail!.publication_id);
      if(saved) setNotice(`Publication ${saved.id} was saved. ${remaining.length} evidence file(s) remain. Retry saving to upload them without creating another publication.`);
    } finally {setBusy(false);}
    return saved;
  }
  const duplicate = Boolean(duplicateId || duplicateDoi && draft.doi === duplicateDoi);
  const warnings = authorWarnings(draft);
  const baseStatus = draft.id ? "SAVED" : duplicate ? "DUPLICATE" : !draft.title || draft.publication_type === "OTHER" ? "AUTHOR_REVIEW" : !draft.publication_date ? "MISSING_DATE" : draft.is_claimable && !draft.authors.some(a=>a.is_claiming_faculty && a.faculty_id) ? "NEEDS_CLAIMANT" : "READY";
  const reviewStatus = batch ? doiReadiness(draft,reviewed,duplicate) : baseStatus === "READY" && warnings.length ? "READY_WITH_WARNINGS" : baseStatus;
  useEffect(()=>{onStatusChange?.(reviewStatus);},[reviewStatus,onStatusChange]);
  useEffect(()=>{onPreviewChange?.(draft,reviewStatus);},[draft,reviewStatus,onPreviewChange]);
  useImperativeHandle(ref,()=>({saveReady:async()=>{if(!isSaveable(reviewStatus) || !reviewed || !formRef.current?.reportValidity()) return;return save();}}));
  return <>{!compact && <div className="page-heading"><div><div className="eyebrow">Publication record</div><h1>{initial ? "Edit publication" : "Add a publication"}</h1><p className="muted">Fetch, review and connect every author to the right person.</p></div><Link href={draft.id ? `/publications/${draft.id}` : "/"}>← {draft.id ? "Back to record" : "Back to overview"}</Link></div>}
    {!initial && !preview && entryMethod === "DOI" && <section className="panel"><div className="step">01 · Start with a DOI</div><h2>Find publication metadata</h2><div className="actions"><label className="field" style={{flex:1}}>DOI or DOI link<textarea rows={4} placeholder="One DOI per line, comma or semicolon" value={lookup} onChange={e=>setLookup(e.target.value)} disabled={Boolean(draft.id)}/></label><button type="button" disabled={busy || !lookup || Boolean(draft.id)} onClick={fetchDoi}>{busy ? "Working…" : "Fetch metadata"}</button><button type="button" className="secondary" onClick={()=>{patch({metadata_source:"MANUAL",source_type:"MANUAL",metadata_fetched_at:null,raw_metadata_json:null,doi:draft.doi || lookup});setNotice("Complete the fields below for a manual publication record.");document.getElementById("bibliography")?.scrollIntoView({behavior:"smooth"});}}>Enter manually</button></div><p className="muted">Paste one DOI or several separated by newlines, commas or semicolons. Lookup creates previews; nothing is saved until review.</p></section>}
    {isBibtex && <div className="notice"><strong>Review status: {reviewStatus}</strong>{draft.id && <> · <Link href={`/publications/${draft.id}`}>Open saved publication</Link></>}<p>Select the claiming faculty explicitly. Complete the publication date and confirm institutional KPI fields.</p></div>}
    {!!warnings.length && <div className="notice" aria-label="Author warnings">{warnings.map(warning=><p key={warning}>{warning}</p>)}<p>These warnings do not block saving. Authors can be classified later.</p></div>}
    {!!differences.length && <section className="panel"><h3>BibTeX and DOI differences</h3><p className="muted">BibTeX values were retained. You can choose a DOI value or edit the field below.</p>{differences.map((difference,i)=><div key={i} className="author-card"><strong>{label(difference.field)}</strong><p>BibTeX: {differenceText(difference.bibtex)}</p><p>DOI: {differenceText(difference.doi)}</p><button type="button" className="secondary small" onClick={()=>patch({[difference.field]:difference.field === "authors" ? (difference.doi as Author[]).map(a=>({...a,is_claiming_faculty:false})) : difference.doi})}>Use DOI {label(difference.field)}</button></div>)}</section>}
    {notice && <div className="notice" role="status">{notice}</div>}
    {error && <div className="error" role="alert">{error.message}{error.detail?.publication_id && <> <Link href={`/publications/${error.detail.publication_id}`}>Open existing publication →</Link></>}{error.detail?.possible_duplicate_ids && <><p>{error.detail.possible_duplicate_ids.map(id=><Link key={id} href={`/publications/${id}`} target="_blank">Review publication #{id} ↗ </Link>)}</p><label className="check"><input type="checkbox" checked={Boolean(draft.duplicate_acknowledged)} onChange={e=>patch({duplicate_acknowledged:e.target.checked})}/>I reviewed these records; save this as a separate publication.</label></>}</div>}
    {draft.raw_bibtex && <details className="panel"><summary>Original BibTeX entry</summary><pre>{draft.raw_bibtex}</pre></details>}
    <form ref={formRef} onSubmit={save}>
      <section className="panel" id="bibliography"><div className="step">02 · Review & edit</div><h2>Bibliographic details</h2><label className="field">Publication type<select value={draft.publication_type} onChange={e=>patch({publication_type:e.target.value})}>{draft.publication_type === "OTHER" && <option value="OTHER">Choose Journal or Conference</option>}{["JOURNAL","CONFERENCE"].map(v=><option key={v} value={v}>{label(v)}</option>)}</select></label><div className="grid">{bibliography.map(([key,title,type])=><label key={key} className={`field ${key === "title" ? "wide" : ""}`}>{title}{["title","publication_date"].includes(key) ? " *" : ""}<input type={type || "text"} required={["title","publication_date"].includes(key)} value={String(draft[key] || (key === "proceedings_title" ? draft.journal_conference_name : "") || "")} onChange={e=>patch({[key]:e.target.value || (key === "title" || key === "publication_date" ? "" : null),...(key === "proceedings_title" ? {journal_conference_name:e.target.value || null} : {})})}/></label>)}</div><p className="muted">Source: {draft.source_type || draft.metadata_source}{draft.metadata_fetched_at ? ` · Fetched ${new Date(draft.metadata_fetched_at).toLocaleString()}` : ""}. Academic year is assigned from the publication date.</p></section>
      <section className="panel"><div className="step">03 · Identify contributors</div><div className="row-between"><h2>Authors & claim ownership</h2><Link href="/masters" target="_blank">Manage faculty and students ↗</Link></div><p className="muted">Authors stay in source order. Confirm suggestions or retain external and unknown authors.</p><button type="button" className="secondary small" onClick={()=>api<Masters>("/masters").then(setMasters).catch(setError)}>Refresh master lists</button>
        {draft.authors.map((a,i)=><div className="author-card" key={i}><div className="author-heading"><span className="author-number">{i+1}</span><strong>{a.author_name_from_source || "New author"}</strong><span className="badge">{a.matching_status === "SUGGESTED" ? "Suggested match · needs confirmation" : label(a.matching_status)}</span></div>
          <div className="grid"><label className="field">Author name<input required value={a.author_name_from_source} onChange={e=>authorPatch(i,{author_name_from_source:e.target.value})}/></label><label className="field">Person type<select value={a.person_type} onChange={e=>authorPatch(i,{person_type:e.target.value as PersonType,faculty_id:null,student_id:null,is_internal:["FACULTY","STUDENT"].includes(e.target.value),is_claiming_faculty:false,matching_status:"CONFIRMED"})}>{["FACULTY","STUDENT","EXTERNAL","UNKNOWN"].map(v=><option key={v}>{v}</option>)}</select></label>
          {(a.person_type === "FACULTY" || a.person_type === "STUDENT") && <label className="field">Matched person<select required value={a.faculty_id || a.student_id || ""} onChange={e=>authorPatch(i,{[a.person_type === "FACULTY" ? "faculty_id" : "student_id"]:Number(e.target.value) || null,matching_status:"CONFIRMED"})}><option value="">Select a person</option>{(a.person_type === "FACULTY" ? masters?.faculty : masters?.students)?.filter(p=>p.is_active || p.id === a.faculty_id || p.id === a.student_id).map(p=><option key={p.id} value={p.id}>{p.name}{p.is_active ? "" : " (inactive)"}</option>)}</select></label>}
          <label className="field">Given name<input value={a.given_name_from_source || ""} onChange={e=>authorPatch(i,{given_name_from_source:e.target.value})}/></label><label className="field">Family name<input value={a.family_name_from_source || ""} onChange={e=>authorPatch(i,{family_name_from_source:e.target.value})}/></label><label className="field">ORCID from source<input value={a.orcid_from_source || ""} onChange={e=>authorPatch(i,{orcid_from_source:e.target.value})}/></label><label className="field wide">Affiliations (one per line)<textarea value={a.affiliation_from_source.join("\n")} onChange={e=>authorPatch(i,{affiliation_from_source:e.target.value.split("\n")})}/></label></div>
          {!!a.suggestions?.length && a.matching_status === "SUGGESTED" && <div className="notice"><strong>Suggested matches</strong>{a.suggestions.map(s=><div className="row-between" key={`${s.person_type}-${s.id}`}><span>{s.name} · {label(s.person_type)} · {Math.round(s.confidence*100)}% · {label(s.reason)}</span><button className="secondary small" type="button" onClick={()=>authorPatch(i,{person_type:s.person_type,faculty_id:s.person_type === "FACULTY" ? s.id : null,student_id:s.person_type === "STUDENT" ? s.id : null,is_internal:true,matching_status:"CONFIRMED"})}>Confirm match</button></div>)}</div>}
          <div className="checks">{a.person_type === "FACULTY" && Boolean(a.faculty_id) && <label><input type="radio" name="claimant" aria-label={`Claiming faculty: ${a.author_name_from_source}`} disabled={!draft.is_claimable || !a.faculty_id} checked={a.is_claiming_faculty} onChange={()=>patch({authors:draft.authors.map((author,n)=>({...author,is_claiming_faculty:n===i}))})}/> Claiming faculty</label>}<label><input type="checkbox" checked={a.is_corresponding_author} onChange={e=>authorPatch(i,{is_corresponding_author:e.target.checked})}/> Corresponding author</label><label><input type="checkbox" checked={a.is_first_author} onChange={e=>authorPatch(i,{is_first_author:e.target.checked})}/> First author</label><button type="button" className="secondary small" disabled={i===0} onClick={()=>{const list=draft.authors.map(a=>({...a}));[list[i-1],list[i]]=[list[i],list[i-1]];authorList(list.map((a,n)=>({...a,author_order:n+1})));}}>Move up</button><button type="button" className="danger small" onClick={()=>authorList(draft.authors.filter((_,n)=>n!==i).map((a,n)=>({...a,author_order:n+1})))}>Remove author</button></div>
        </div>)}
        <div className="actions"><button type="button" className="secondary" onClick={()=>authorList([...draft.authors,blankAuthor(draft.authors.length+1)])}>+ Add author</button><label className="check"><input type="checkbox" checked={!draft.is_claimable} onChange={e=>{const authors=draft.authors.map(a=>({...a,is_claiming_faculty:false}));const faculty=authors.filter(a=>a.faculty_id);if(!isBibtex && !batch && !e.target.checked && faculty.length===1) faculty[0].is_claiming_faculty=true;patch({is_claimable:!e.target.checked,authors});}}/> Explicitly non-claimable</label></div>
      </section>
      <section className="panel"><div className="step">04 · Institutional KPI fields</div><h2>Indexing & classification</h2><p className="muted">Confirm indexing using institutional evidence. DOI metadata does not verify indexing.</p><div className="checks">{INDEXING.map(value=><label key={value}><input type="checkbox" checked={draft.indexing.includes(value)} onChange={e=>patch({indexing:e.target.checked ? ["NONE","UNKNOWN"].includes(value) ? [value] : [...draft.indexing.filter(v=>!["NONE","UNKNOWN"].includes(v)),value] : draft.indexing.filter(v=>v!==value)})}/>{label(value)}</label>)}</div><div className="grid" style={{marginTop:20}}><label className="field">Classification<select value={draft.classification || "UNKNOWN"} onChange={e=>patch({classification:e.target.value})}>{CLASSIFICATIONS.map(v=><option key={v} value={v}>{label(v)}</option>)}</select></label><label className="field">Impact factor<input type="number" min="0" step="any" value={draft.impact_factor ?? ""} onChange={e=>patch({impact_factor:e.target.value === "" ? null : Number(e.target.value)})}/></label><label className="field">Quartile<select value={draft.quartile || ""} onChange={e=>patch({quartile:e.target.value || null})}><option value="">Not applicable / Unknown</option>{QUARTILES.map(v=><option value={v} key={v}>{label(v)}</option>)}</select></label><label className="field">Remarks<textarea value={draft.remarks || ""} onChange={e=>patch({remarks:e.target.value})}/></label><label className="check"><input type="checkbox" checked={draft.is_active} onChange={e=>patch({is_active:e.target.checked})}/> Active record</label></div></section>
      <section className="panel"><div className="step">05 · Attach supporting documents</div><h2>Evidence</h2><p className="muted">PDF, PNG, JPG or DOCX · Up to 25 MB each. Files upload when the reviewed record is saved.</p>{draft.evidence?.map(e=><p key={e.id}><a href={`/api/publications/${draft.id}/evidence/${e.id}`} target="_blank" rel="noreferrer">{e.original_filename} ↗</a> · {label(e.evidence_type)}</p>)}<div className="grid"><label className="field">Evidence type<select value={fileType} onChange={e=>setFileType(e.target.value)}>{["PUBLISHED_PAPER","FIRST_PAGE","INDEXING_PROOF","ACCEPTANCE_LETTER","PUBLICATION_PROOF","CONFERENCE_PAPER","PROCEEDINGS_FIRST_PAGE","CERTIFICATE","CONFERENCE_PROGRAM","OTHER"].map(v=><option key={v} value={v}>{label(v)}</option>)}</select></label><label className="field">Choose evidence files<input type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.docx" onChange={e=>{const chosen=Array.from(e.target.files || []);if(chosen.some(f=>f.size>25*1024*1024 || !f.size))setError(new ApiError("Choose nonempty files up to 25 MB each."));else setFiles(prev=>[...prev,...chosen.map(file=>({file,type:fileType}))]);e.target.value="";}}/></label></div>{files.map((f,i)=><div className="row-between pending-file" key={i}><span>{f.file.name} · {label(f.type)}</span><button type="button" className="secondary small" onClick={()=>setFiles(files.filter((_,n)=>n!==i))}>Remove queued file</button></div>)}</section>
      <div className="savebar">{!onApply && <label className="check"><input required type="checkbox" checked={reviewed} onChange={e=>setReviewed(e.target.checked)}/> I reviewed the metadata, author mappings and claiming faculty.</label>}<button disabled={!onApply && (busy || !reviewed || (!isSaveable(reviewStatus) && reviewStatus !== "SAVED"))} type="submit">{onApply ? "Return to queue" : busy ? "Saving…" : draft.id ? "Save changes" : "Save publication"}</button></div>
    </form>
  </>;
}
