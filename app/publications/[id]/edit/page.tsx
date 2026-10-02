"use client";
import {useEffect,useState} from "react";
import {useParams} from "next/navigation";
import PublicationEditor from "@/components/PublicationEditor";
import {api,Publication} from "@/lib/api";
export default function EditPublication() {
  const {id}=useParams<{id:string}>();const [paper,setPaper]=useState<Publication>();const [error,setError]=useState("");
  useEffect(()=>{api<Publication>(`/publications/${id}`).then(setPaper).catch(e=>setError(e.message));},[id]);
  return error ? <div className="error" role="alert">{error}</div> : paper ? <PublicationEditor initial={paper}/> : <p role="status">Loading publication…</p>;
}
