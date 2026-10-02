"use client";
import {useState} from "react";
import {label} from "@/lib/api";
export type PendingEvidence={file:File;type:string};
export default function EvidenceQueue({files,setFiles,categories}:{files:PendingEvidence[];setFiles:(files:PendingEvidence[])=>void;categories:string[]}){
  const [category,setCategory]=useState(categories[0]);const [error,setError]=useState("");
  return <><p className="muted">PDF, PNG, JPG or DOCX · Up to 25 MB each. Files upload after the record is saved.</p>{error&&<div className="error" role="alert">{error}</div>}<div className="grid"><label className="field">Evidence category<select value={category} onChange={e=>setCategory(e.target.value)}>{categories.map(c=><option key={c} value={c}>{label(c)}</option>)}</select></label><label className="field">Choose evidence files<input type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.docx" onChange={e=>{const selected=Array.from(e.target.files||[]);if(selected.some(f=>!f.size||f.size>25*1024*1024))setError("Choose nonempty files of 25 MB or less.");else{setError("");setFiles([...files,...selected.map(file=>({file,type:category}))]);}e.target.value="";}}/></label></div>{files.map((item,i)=><div className="row-between pending-file" key={i}><span>{item.file.name} · {label(item.type)}</span><button className="secondary small" type="button" onClick={()=>setFiles(files.filter((_,n)=>n!==i))}>Remove queued file</button></div>)}</>;
}
