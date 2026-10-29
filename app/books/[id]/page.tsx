"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, label } from "@/lib/api";
import { Book } from "@/lib/books";
import { SCOPES } from "@/lib/patents";

export default function BookDetail() {
  const { id } = useParams<{ id: string }>();
  const [work, setWork] = useState<Book>();
  const [error, setError] = useState("");
  const [back, setBack] = useState("/books");
  const [deactivating, setDeactivating] = useState(false);

  async function loadWork() {
    try {
      setWork(await api<Book>(`/books/${id}`));
    } catch (requestError) {
      setError((requestError as Error).message);
    }
  }

  useEffect(() => {
    void loadWork();
    setBack(`/books${window.location.search}`);
  }, [id]);

  async function removeEvidence(identity: number) {
    if (!window.confirm("Remove this evidence file?")) return;
    try {
      await api(`/books/${id}/evidence/${identity}`, { method: "DELETE" });
      await loadWork();
    } catch (requestError) {
      setError((requestError as Error).message);
    }
  }

  async function deactivate() {
    if (!work || !window.confirm("Deactivate this Book / Chapter? It will remain available when inactive records are included.")) return;
    setDeactivating(true);
    setError("");
    try {
      await api(`/books/${work.id}`, { method: "DELETE" });
      await loadWork();
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setDeactivating(false);
    }
  }

  return <>
    {error && <div className="error" role="alert">{error}</div>}
    {!work && !error && <p>Loading work…</p>}
    {work && <>
      <div className="page-heading">
        <div><div className="eyebrow">{label(work.work_type)}{!work.is_active && " · Inactive"}</div><h1>{work.title}</h1></div>
        <div className="actions">
          <Link href={back}>← Back to report</Link>
          <Link className="button" href={`/books/${id}/edit`}>Edit work</Link>
          {work.is_active && <button className="danger" disabled={deactivating} onClick={deactivate}>{deactivating ? "Deactivating…" : "Deactivate"}</button>}
        </div>
      </div>
      <section className="panel"><h2>Work Details</h2><dl className="detail-grid">{(["parent_book_title", "chapter_number", "publisher", "publication_date", "edition", "volume", "publication_year", "classification", "metadata_source", "metadata_fetched_at", "page_range", "isbn", "eisbn", "doi"] as const).filter((key) => work.work_type === "BOOK_CHAPTER" ? true : !["parent_book_title", "chapter_number", "page_range"].includes(key)).map((key) => <div key={key}><dt>{label(key)}</dt><dd>{work[key] || "—"}</dd></div>)}</dl>{work.url && /^https?:\/\//i.test(work.url) && <p><a href={work.url} target="_blank" rel="noreferrer">Publisher / Publication URL ↗</a></p>}<p>{work.remarks}</p></section>
      <section className="panel"><h2>Contributors</h2>{work.work_type === "BOOK_CHAPTER" && <p className="muted">Authors wrote this chapter. Editors are editors of the parent book.</p>}{work.contributors.map((contributor) => <div key={contributor.contributor_order} className={`author-card ${contributor.is_current_department ? "local" : ""}`}><div className="author-heading"><span className="author-number">{contributor.contributor_order}</span><strong>{contributor.contributor_name}</strong><span className="badge">{label(contributor.role)}</span><span className="badge">{label(contributor.person_type)}</span><span className="badge">{SCOPES[contributor.institution_scope]}</span>{contributor.is_claiming_faculty && <span className="badge">Claiming Faculty</span>}</div><p>{contributor.institution_name || "Institution unknown"} · {contributor.department_name || "Department unknown"}</p><p className="muted">{contributor.person_name && `Master reference: ${contributor.person_name} · `}{contributor.employee_or_roll_number || "No employee / roll number recorded"}</p></div>)}</section>
      <section className="panel"><h2>Collaboration</h2><div className="checks"><span>Department faculty: {work.current_department_faculty_count}</span><span>Department students: {work.current_department_student_count}</span><span>Other VCE departments: {work.same_institution_other_department_count}</span><span>External contributors: {work.external_contributor_count}</span></div></section>
      <section className="panel"><div className="row-between"><h2>Evidence · {work.evidence_count} files</h2><Link href={`/books/${id}/edit`}>Add evidence →</Link></div>{work.evidence?.map((evidence) => <div className="row-between pending-file" key={evidence.id}><div><strong>{evidence.original_filename}</strong><div className="muted">{label(evidence.evidence_type)} · {Math.ceil(evidence.size_bytes / 1024)} KB</div></div><div className="actions"><a href={`/api/books/${id}/evidence/${evidence.id}`} target="_blank" rel="noreferrer">View</a><a href={`/api/books/${id}/evidence/${evidence.id}?download=true`}>Download</a><button className="danger small" onClick={() => removeEvidence(evidence.id)}>Remove</button></div></div>)}{!work.evidence?.length && <p className="muted">No evidence attached.</p>}</section>
      <section className="panel"><details><summary>Record changes</summary>{work.change_log?.map((change) => <p key={change.id}>{label(change.action)} · {new Date(change.changed_at).toLocaleString()}</p>)}</details></section>
    </>}
  </>;
}
