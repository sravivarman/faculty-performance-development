"use client";
import {useEffect,useState} from "react";
import {useParams} from "next/navigation";
import PatentEditor from "@/components/PatentEditor";
import {api} from "@/lib/api";
import {Patent} from "@/lib/patents";
export default function EditPatent(){const {id}=useParams<{id:string}>();const [patent,setPatent]=useState<Patent>();const [error,setError]=useState("");useEffect(()=>{api<Patent>(`/patents/${id}`).then(setPatent).catch(e=>setError(e.message));},[id]);return error?<div className="error" role="alert">{error}</div>:patent?<PatentEditor initial={patent}/>:<p role="status">Loading patent…</p>;}
