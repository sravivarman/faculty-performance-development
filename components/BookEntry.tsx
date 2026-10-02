"use client";
import {useState} from 'react';
import Link from 'next/link';
import BookEditor from './BookEditor';
import BookDOIQueue from './BookDOIQueue';
import {blankBook} from '@/lib/books';
export default function BookEntry(){
  const [mode,setMode]=useState('DOI');const [busy,setBusy]=useState(false);const [manual,setManual]=useState(blankBook);
  return <><div className="page-heading"><div><div className="eyebrow">Books / Chapters</div><h1>Add Book / Book Chapter</h1><p className="muted">Fetch one or many DOIs, review each record, then add ready items.</p></div><Link href="/books">← Back to books</Link></div><div className="actions" aria-label="Entry method"><button disabled={busy} aria-pressed={mode==='DOI'} className={mode==='DOI'?'':'secondary'} onClick={()=>setMode('DOI')}>Add by DOI</button><button disabled={busy} aria-pressed={mode==='MANUAL'} className={mode==='MANUAL'?'':'secondary'} onClick={()=>setMode('MANUAL')}>Manual Entry</button></div><div hidden={mode!=='DOI'}><BookDOIQueue onBusy={setBusy}/></div>{mode==='MANUAL'&&<BookEditor initial={manual} onDraftChange={setManual} hideLookup hideHeader/>}</>;
}
