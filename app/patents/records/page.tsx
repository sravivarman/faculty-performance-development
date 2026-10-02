"use client";
import {useEffect,useState} from "react";
import Link from "next/link";
import {api} from "@/lib/api";
import {Patent} from "@/lib/patents";
import PatentTypeSelect from "@/components/PatentTypeSelect";
import PatentTable from "@/components/PatentTable";
export default function PatentRegistry(){const [records,setRecords]=useState<Patent[]>([]);const [patentType,setPatentType]=useState("");const [error,setError]=useState("");useEffect(()=>{api<Patent[]>(`/patents?department_only=false&include_inactive=true&${new URLSearchParams(patentType?{patent_type:patentType}:{})}`).then(setRecords).catch(e=>setError(e.message));},[patentType]);return <><div className="page-heading"><div><h1>All patent records</h1><p className="muted">Includes early undated entries, inactive records and patents outside the current department. This registry is not a KPI report.</p></div><Link className="button" href="/patents/new">+ Add patent</Link></div><Link href="/patents">← Patent reporting</Link>{error&&<div className="error" role="alert">{error}</div>}<section className="panel"><div className="row-between"><PatentTypeSelect filter value={patentType} onChange={setPatentType}/><a className="button secondary" href={`/api/patent-export?department_only=false&include_inactive=true&${new URLSearchParams(patentType?{patent_type:patentType}:{})}`}>Export CSV</a></div><PatentTable patents={records}/></section></>;}
