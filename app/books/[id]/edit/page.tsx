"use client";
import {useEffect,useState} from "react";
import {useParams} from "next/navigation";
import BookEditor from "@/components/BookEditor";
import {api} from "@/lib/api";
import {Book} from "@/lib/books";
export default function EditBook(){const {id}=useParams<{id:string}>();const [book,setBook]=useState<Book>();const [error,setError]=useState("");useEffect(()=>{api<Book>(`/books/${id}`).then(setBook).catch(e=>setError(e.message));},[id]);return error?<div className="error" role="alert">{error}</div>:book?<BookEditor initial={book}/>:<p role="status">Loading book…</p>;}
