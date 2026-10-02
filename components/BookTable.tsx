import Link from "next/link";
import {Book} from "@/lib/books";
export default function BookTable({books,query=""}:{books:Book[];query?:string}) {
  return <div className="table-wrap"><table><thead><tr>{["Work / Book title","Faculty Authors","Student Authors","Other Institution Authors","Publisher / ISBN","Publication Date","Claiming Faculty","Evidence","Details"].map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{books.map(b=>{
    const names=(test:(c:Book["contributors"][number])=>boolean)=>[...new Set(b.contributors.filter(c=>c.role==="AUTHOR"&&test(c)).map(c=>c.person_name||c.contributor_name))].join(", ")||"—";
    return <tr key={b.id}><td><strong>{b.title}</strong><small>{b.work_type==="BOOK"?"Book":"Chapter"}{b.parent_book_title&&` · ${b.parent_book_title}`}</small></td><td>{names(c=>!!c.is_current_department&&c.person_type==="FACULTY")}</td><td>{names(c=>!!c.is_current_department&&c.person_type==="STUDENT")}</td><td>{names(c=>!c.is_current_department)}<small>{b.contributors.filter(c=>c.role==="EDITOR").map(c=>`Editor: ${c.contributor_name}`).join(", ")}</small></td><td>{b.publisher}<small>{b.isbn||b.eisbn||"ISBN not recorded"}</small></td><td>{b.publication_date}</td><td>{b.contributors.find(c=>c.is_claiming_faculty)?.person_name||b.contributors.find(c=>c.is_claiming_faculty)?.contributor_name||"—"}</td><td>{b.evidence_count??0}</td><td><Link href={`/books/${b.id}${query?`?${query}`:""}`}>View Details →</Link></td></tr>;
  })}</tbody></table>{!books.length&&<p className="muted">No works match these filters.</p>}</div>;
}
