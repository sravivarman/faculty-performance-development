"use client";
import {useEffect,useState} from "react";
import Link from "next/link";
import {useParams} from "next/navigation";
import PublicationEditor from "@/components/PublicationEditor";
import {api,Publication} from "@/lib/api";
export default function EditPublication() {
  const {id}=useParams<{id:string}>();const [paper,setPaper]=useState<Publication>();const [error,setError]=useState("");
  useEffect(()=>{if(!id)return;api<Publication>(`/publications/${id}`).then(setPaper).catch(e=>setError(e.message));},[id]);
  if(error) return <><Link href="/publications">← Back to publications</Link><div className="error" role="alert">{error}</div></>;
  return paper ? <PublicationEditor initial={paper}/> : <p role="status">Loading publication…</p>;
}
