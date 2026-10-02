"use client";
import {useEffect,useState} from "react";
import Link from "next/link";
import {api} from "@/lib/api";
import {Book} from "@/lib/books";
import BookTable from "@/components/BookTable";
export default function AllBooks(){
  const [books,setBooks]=useState<Book[]>([]);const [error,setError]=useState("");const [inactive,setInactive]=useState(false);
  useEffect(()=>{let active=true;api<Book[]>(`/books?department_only=false&include_inactive=${inactive}`).then(b=>{if(active)setBooks(b);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[inactive]);
  return <><div className="page-heading"><div><h1>All Books / Chapters</h1><p className="muted">Includes works with unresolved contributors and parent-book editors only. The department report applies authorship and date rules.</p></div><div className="actions"><Link href="/books">Department report</Link><Link className="button" href="/books/new">+ Add Book / Book Chapter</Link></div></div>{error&&<div role="alert" className="error">{error}</div>}<section className="panel"><label className="check"><input type="checkbox" checked={inactive} onChange={e=>setInactive(e.target.checked)}/>Include inactive records</label><BookTable books={books}/></section></>;
}
