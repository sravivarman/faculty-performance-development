"use client";

import {ChangeEvent, useEffect, useMemo, useState} from "react";
import {api, Author, Masters, Publication} from "@/lib/api";
import {
  ContributorDecision, downloadReviewPackage, fingerprintFile, makeReviewPackage, recordIdentity,
  ReviewPackageError, ReviewRecord, ReviewSession, ReviewStatus, reviewStorageKey, validateReviewPackage,
} from "@/lib/bulk-publication-review";

export type ReviewSourceEntry = {
  entry_number: number; citation_key?: string | null; publication?: Partial<Publication> & {authors?: Author[]};
  duplicate_status: string; publication_date_status: string; missing_metadata: string[];
  import_readiness?: {blockers: string[]; status: string};
  document_classification?: {suggested_module?: string};
  scopus_match?: {status?: string; csv_record?: {eid?: string | null} | null};
  date_enrichment?: {verification?: {suggested_date?: {date: string; precision: string; source: string; source_url: string; date_type: string} | null}};
};
export type ReviewSourceAnalysis = {file_name: string; entries: ReviewSourceEntry[]};

type Props = {
  analysis: ReviewSourceAnalysis;
  bibtexFile: File;
  scopusFile?: File;
  onVerify: (entries: ReviewSourceEntry[]) => Promise<void>;
};

const STEPS = ["identity", "duplicate", "classification", "metadata", "date", "contributors", "claimant"] as const;
const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;
const asDateEvidence = (entry: ReviewSourceEntry) => entry.date_enrichment?.verification || undefined;
const restoreFailure = (error: unknown) => {
  if (error instanceof ReviewPackageError) return `${error.code}: ${error.message}`;
  return `RESTORE_FAILED: ${(error as Error).message || "The review package could not be restored."}`;
};

function initialContributor(author: Author): ContributorDecision {
  if (author.person_type === "FACULTY" && author.faculty_id && author.matching_status !== "SUGGESTED") return {kind: "FACULTY", person_id: author.faculty_id, display_name: author.author_name_from_source};
  if (author.person_type === "STUDENT" && author.student_id && author.matching_status !== "SUGGESTED") return {kind: "STUDENT", person_id: author.student_id, display_name: author.author_name_from_source};
  if (author.person_type === "EXTERNAL") return {kind: "EXTERNAL", display_name: author.author_name_from_source};
  return {kind: "UNRESOLVED", display_name: author.author_name_from_source};
}

function dateSuggestion(record: ReviewRecord) {
  const verification = record.date_evidence as {suggested_date?: {date: string; precision: string; source: string; source_url: string; date_type: string}} | undefined;
  return verification?.suggested_date;
}

function recompute(record: ReviewRecord): ReviewRecord {
  const publication = record.draft;
  const authors = publication.authors || [];
  const decisions = Object.values(record.contributors);
  const blockers: string[] = [];
  if (record.duplicate_status !== "NO_DUPLICATE_DETECTED") blockers.push("Duplicate or possible duplicate requires review outside this workspace.");
  if (record.source_identity === "AMBIGUOUS" || record.source_identity === "IDENTITY_CONFLICT") blockers.push("Source identity requires further review.");
  if (!["JOURNAL", "CONFERENCE"].includes(publication.publication_type || "")) blockers.push("Only Journal and Conference drafts can be prepared for Stage 2B.");
  if (!publication.title?.trim() || !publication.publication_date || !(publication.journal_conference_name || publication.proceedings_title || publication.conference_name)) blockers.push("Required title, venue, or exact publication date is incomplete.");
  const verifiedDate = dateSuggestion(record);
  const isManualDateProposal = Boolean(publication.publication_date && publication.publication_date !== record.original.publication_date && !verifiedDate);
  if (isManualDateProposal && (!record.manual_date?.evidence?.trim() || !record.manual_date.date_type)) blockers.push("A manually proposed date needs an evidence source and date type.");
  if (verifiedDate && publication.publication_date && publication.publication_date !== verifiedDate.date && !record.manual_date?.explanation?.trim()) blockers.push("Explain why the proposed date differs from verified provider metadata.");
  if (decisions.some(decision => decision.kind === "UNRESOLVED")) blockers.push("One or more contributors remain unresolved.");
  const confirmedFaculty = authors.filter(author => record.contributors[String(author.author_order)]?.kind === "FACULTY" && record.contributors[String(author.author_order)]?.person_id);
  if (!record.claiming_faculty_id || !confirmedFaculty.some(author => record.contributors[String(author.author_order)]?.person_id === record.claiming_faculty_id)) blockers.push("Select exactly one confirmed internal Faculty claimant.");
  const allStepsConfirmed = STEPS.every(step => record.confirmed_steps[step] === "CONFIRMED");
  const reviewStatus: ReviewStatus = blockers.length ? (Object.keys(record.confirmed_steps).length ? "BLOCKED" : "NOT_REVIEWED") : allStepsConfirmed ? "READY_FOR_FINAL_VALIDATION" : "IN_REVIEW";
  return {...record, warnings: blockers, review_status: reviewStatus};
}

function recomputeRestored(record: ReviewRecord): ReviewRecord {
  const recomputed = recompute(record);
  // A package's final validation is restored only when all protected draft and
  // review conditions still pass. A later Stage 2B must still revalidate live
  // duplicate and Master-data state before any persistence is possible.
  return record.review_status === "VALIDATED_FOR_STAGE_2B" && recomputed.review_status === "READY_FOR_FINAL_VALIDATION"
    ? {...recomputed, review_status: "VALIDATED_FOR_STAGE_2B"}
    : recomputed;
}

function entryRecord(entry: ReviewSourceEntry, sourceFingerprint: string): ReviewRecord {
  const publication = clone(entry.publication || {});
  const authors = publication.authors || [];
  const eid = entry.scopus_match?.csv_record?.eid;
  return recompute({
    record_id: recordIdentity(sourceFingerprint, entry.entry_number, publication.doi, eid), entry_number: entry.entry_number,
    source_doi: publication.doi, source_eid: eid, source_title: publication.title || `Entry ${entry.entry_number}`,
    duplicate_status: entry.duplicate_status, source_identity: entry.scopus_match?.status || "BIBTEX_ONLY",
    suggested_module: entry.document_classification?.suggested_module, original: clone(publication), draft: publication,
    contributors: Object.fromEntries(authors.map(author => [String(author.author_order), initialContributor(author)])),
    confirmed_steps: {}, date_evidence: asDateEvidence(entry), review_status: "NOT_REVIEWED", warnings: [],
  });
}

function sessionFromAnalysis(analysis: ReviewSourceAnalysis, bibFingerprint: string, scopus?: {name: string; fingerprint: string}): ReviewSession {
  const now = new Date().toISOString();
  return {
    schema: "vce.bulk-publication-review", version: 1, session_id: crypto.randomUUID(), created_at: now, updated_at: now,
    analysis_version: "stage-1d", readiness_policy_version: "stage-2a-1",
    bibtex: {name: analysis.file_name, fingerprint: bibFingerprint}, scopus,
    records: analysis.entries.map(entry => entryRecord(entry, bibFingerprint)),
  };
}

export default function BulkPublicationReviewWorkspace({analysis, bibtexFile, scopusFile, onVerify}: Props) {
  const [session, setSession] = useState<ReviewSession>();
  const [masters, setMasters] = useState<Masters>();
  const [selected, setSelected] = useState<string[]>([]);
  const [active, setActive] = useState<string>();
  const [filter, setFilter] = useState("POTENTIALLY_NEW");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("SOURCE");
  const [tablePage, setTablePage] = useState(1);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { api<Masters>("/masters").then(setMasters).catch(error => setNotice(`Master data could not be read: ${error.message}`)); }, []);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const fingerprint = await fingerprintFile(bibtexFile);
      const existing = localStorage.getItem(reviewStorageKey(fingerprint));
      if (cancelled) return;
      const scopus = scopusFile ? {name: scopusFile.name, fingerprint: await fingerprintFile(scopusFile)} : undefined;
      if (existing) {
        try { setSession(await validateReviewPackage(JSON.parse(existing), {bibtex: fingerprint, scopus: scopus?.fingerprint})); setNotice("Restored browser-local review progress for these source files."); return; }
        catch { localStorage.removeItem(reviewStorageKey(fingerprint)); }
      }
      if (!cancelled) setSession(sessionFromAnalysis(analysis, fingerprint, scopus));
    })().catch(error => setNotice(`Review workspace could not be initialized: ${error.message}`));
    return () => { cancelled = true; };
  // The workspace is mounted only after an analysis completes. Keeping this keyed
  // to the source files prevents DOI-enrichment responses from recreating a
  // reviewer session in the middle of a review.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bibtexFile, scopusFile]);
  useEffect(() => {
    if (!session) return;
    let cancelled = false;
    void makeReviewPackage(session).then(packet => {
      if (!cancelled) localStorage.setItem(reviewStorageKey(session.bibtex.fingerprint), JSON.stringify(packet));
    }).catch(() => setNotice("Browser-local review progress could not be saved. Export a review session before leaving this page."));
    return () => { cancelled = true; };
  }, [session]);
  useEffect(() => {
    if (!session) return;
    setSession(current => current && {
      ...current, records: current.records.map(record => {
        const source = analysis.entries.find(entry => entry.entry_number === record.entry_number);
        if (!source || record.source_doi !== source.publication?.doi) return record;
        return recompute({...record, date_evidence: asDateEvidence(source), confirmed_steps: {...record.confirmed_steps, date: "NOT_STARTED"}});
      }), updated_at: new Date().toISOString(),
    });
  }, [analysis]);

  const update = (recordId: string, change: (record: ReviewRecord) => ReviewRecord) => setSession(current => current ? {
    ...current, updated_at: new Date().toISOString(), records: current.records.map(record => {
      if (record.record_id !== recordId) return record;
      const changed = change(record);
      // A draft edit is a new reviewer decision, so final validation cannot
      // survive a content, contributor, claimant, or date change.
      return recompute({...changed, review_status: changed.review_status === "VALIDATED_FOR_STAGE_2B" ? "IN_REVIEW" : changed.review_status});
    }),
  } : current);
  const validate = (recordId: string) => setSession(current => current ? {
    ...current, updated_at: new Date().toISOString(), records: current.records.map(record => {
      if (record.record_id !== recordId) return record;
      const checked = recompute(record);
      return checked.review_status === "READY_FOR_FINAL_VALIDATION" ? {...checked, review_status: "VALIDATED_FOR_STAGE_2B"} : checked;
    }),
  } : current);
  const rows = useMemo(() => {
    const search = query.trim().toLowerCase();
    return (session?.records || []).filter(record =>
      (filter === "ALL" || filter === "POTENTIALLY_NEW" && record.duplicate_status === "NO_DUPLICATE_DETECTED" ||
      filter === "READY" && record.review_status === "READY_FOR_FINAL_VALIDATION" || filter === "VALIDATED" && record.review_status === "VALIDATED_FOR_STAGE_2B" ||
      filter === "DATE" && !record.draft.publication_date || filter === "CLAIMANT" && !record.claiming_faculty_id ||
      filter === "CONTRIBUTORS" && Object.values(record.contributors).some(decision => decision.kind === "UNRESOLVED") ||
      filter === "EXISTING" && record.duplicate_status === "EXISTING_DATABASE" || filter === "BLOCKED" && record.review_status === "BLOCKED") &&
      (!search || [record.draft.title, record.draft.doi, record.source_eid, record.source_title].join(" ").toLowerCase().includes(search))
    ).sort((left, right) => sort === "TITLE" ? (left.draft.title || left.source_title).localeCompare(right.draft.title || right.source_title) : sort === "YEAR" ? (right.draft.publication_date || "").localeCompare(left.draft.publication_date || "") : left.entry_number - right.entry_number);
  }, [session, filter, query, sort]);
  const tablePages = Math.max(1, Math.ceil(rows.length / 25));
  const visibleRows = rows.slice((tablePage - 1) * 25, tablePage * 25);
  const activeRecord = session?.records.find(record => record.record_id === active);
  const sourceByNumber = new Map(analysis.entries.map(entry => [entry.entry_number, entry]));
  const summary = useMemo(() => {
    const records = session?.records || [];
    return {total: records.length, existing: records.filter(record => record.duplicate_status === "EXISTING_DATABASE").length,
      candidates: records.filter(record => record.duplicate_status === "NO_DUPLICATE_DETECTED").length,
      inReview: records.filter(record => record.review_status === "IN_REVIEW").length,
      dates: records.filter(record => Boolean(dateSuggestion(record))).length,
      missingDates: records.filter(record => !record.draft.publication_date).length,
      ready: records.filter(record => record.review_status === "READY_FOR_FINAL_VALIDATION").length,
      validated: records.filter(record => record.review_status === "VALIDATED_FOR_STAGE_2B").length};
  }, [session]);

  async function verify(records: ReviewRecord[]) {
    const seenDois = new Set<string>();
    const entries = records.map(record => sourceByNumber.get(record.entry_number)).filter((entry): entry is ReviewSourceEntry => Boolean(entry)).filter(entry => {
      const doi = entry.publication?.doi?.trim().toLowerCase();
      if (!doi || seenDois.has(doi)) return false;
      seenDois.add(doi); return true;
    });
    if (!entries.length) return;
    setBusy(true); setNotice("");
    try { await onVerify(entries.slice(0, 25)); setNotice(`Requested DOI verification for ${Math.min(entries.length, 25)} selected record(s). The per-action limit is 25.`); }
    catch (error) { setNotice(`DOI verification could not be completed: ${(error as Error).message}`); }
    finally { setBusy(false); }
  }
  async function exportSession() {
    if (!session) return;
    const packet = await makeReviewPackage(session); downloadReviewPackage(packet);
    setNotice("Downloaded an integrity-checked review package. It contains research metadata and reviewer decisions; keep it securely.");
  }
  async function restore(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]; if (!file || !session) return;
    if (file.size > 15 * 1024 * 1024) { setNotice("PACKAGE_TOO_LARGE: The review package is too large to restore in this browser. Export a smaller, trusted package."); event.target.value = ""; return; }
    try { const restored = await validateReviewPackage(JSON.parse(await file.text()), {bibtex: session.bibtex.fingerprint, scopus: session.scopus?.fingerprint}); setSession({...restored, records: restored.records.map(recomputeRestored)}); setNotice("Restored review package. Duplicate, Faculty Master, and source findings must be revalidated by Stage 2B before any future import."); }
    catch (error) { setNotice(`Review package was rejected: ${restoreFailure(error)}`); }
    finally { event.target.value = ""; }
  }
  if (!session) return <section className="panel" aria-label="Bulk publication review workspace"><p role="status">Preparing browser-local review workspace…</p></section>;

  const selectable = rows.filter(record => record.duplicate_status === "NO_DUPLICATE_DETECTED" && ["JOURNAL", "CONFERENCE"].includes(record.draft.publication_type || ""));
  return <section className="panel" aria-label="Bulk publication review workspace">
    <div className="row-between"><div><div className="step">Review preparation only</div><h2>Bulk Publication Review Workspace</h2><p className="muted">Review decisions are stored only in this browser and in an explicitly downloaded package. No publications have been saved.</p></div><div className="actions"><button type="button" className="secondary" onClick={exportSession}>Export Review Session</button><label className="secondary" role="button">Import Review Session<input aria-label="Import Review Session package" type="file" accept="application/json,.json" hidden onChange={restore}/></label><button type="button" className="danger small" onClick={() => { localStorage.removeItem(reviewStorageKey(session.bibtex.fingerprint)); setSession(sessionFromAnalysis(analysis, session.bibtex.fingerprint, session.scopus)); setNotice("Deleted browser-local review decisions for this source fingerprint."); }}>Delete local review data</button></div></div>
    <p className="notice"><strong>Review Preparation Only — No Publications Have Been Saved</strong></p>{notice && <p role="status">{notice}</p>}
    <div className="analysis-summary-cards">{[["Total records", summary.total], ["Existing database matches", summary.existing], ["Potentially new", summary.candidates], ["Under review", summary.inReview], ["Date evidence found", summary.dates], ["Missing proposed date", summary.missingDates], ["Ready for final validation", summary.ready], ["Validated for Stage 2B", summary.validated]].map(([label, value]) => <div className="analysis-card" key={String(label)}><span>{label}</span><strong>{value}</strong></div>)}</div>
    <div className="actions" style={{marginTop: 12}}><label className="field">Find candidates<input value={query} onChange={event => { setQuery(event.target.value); setTablePage(1); }} placeholder="Title, DOI, or Scopus EID"/></label><label className="field">Review filter<select value={filter} onChange={event => { setFilter(event.target.value); setTablePage(1); }}>{[["POTENTIALLY_NEW", "Potentially new"], ["ALL", "All records"], ["DATE", "Missing date"], ["CONTRIBUTORS", "Contributors pending"], ["CLAIMANT", "Claimant pending"], ["READY", "Ready for final validation"], ["VALIDATED", "Validated for Stage 2B"], ["EXISTING", "Existing database"], ["BLOCKED", "Blocked"]].map(([value, name]) => <option value={value} key={value}>{name}</option>)}</select></label><label className="field">Sort records<select value={sort} onChange={event => { setSort(event.target.value); setTablePage(1); }}><option value="SOURCE">Original source order</option><option value="TITLE">Title</option><option value="YEAR">Proposed publication date</option></select></label><button type="button" className="secondary" disabled={!selected.length || busy} onClick={() => verify((session.records || []).filter(record => selected.includes(record.record_id)))}>{busy ? "Verifying…" : `Verify selected DOI records (${selected.length})`}</button><button type="button" className="secondary" disabled={busy} onClick={() => verify(selectable.filter(record => !record.draft.publication_date))}>Verify next eligible batch (max 25)</button></div>
    <div className="table-wrap" style={{marginTop: 12}}><table><thead><tr><th><input aria-label="Select review records" type="checkbox" checked={selectable.length > 0 && selectable.every(record => selected.includes(record.record_id))} onChange={event => setSelected(event.target.checked ? selectable.map(record => record.record_id) : [])}/></th>{["Title", "Year", "Type", "Duplicate", "Date", "Contributors", "Claimant", "Preparation status", "Review"].map(value => <th key={value}>{value}</th>)}</tr></thead><tbody>{visibleRows.map(record => <tr key={record.record_id}><td><input aria-label={`Select ${record.source_title}`} type="checkbox" disabled={!selectable.some(candidate => candidate.record_id === record.record_id)} checked={selected.includes(record.record_id)} onChange={event => setSelected(current => event.target.checked ? [...current, record.record_id] : current.filter(id => id !== record.record_id))}/></td><td>{record.draft.title || record.source_title}</td><td>{record.draft.publication_date?.slice(0, 4) || "—"}</td><td>{record.draft.publication_type || record.suggested_module || "—"}</td><td>{record.duplicate_status}</td><td>{record.draft.publication_date || "Missing"}</td><td>{Object.values(record.contributors).some(decision => decision.kind === "UNRESOLVED") ? "Review required" : "Confirmed"}</td><td>{record.claiming_faculty_id ? "Selected" : "Required"}</td><td><span className="badge">{record.review_status}</span></td><td><button type="button" className="secondary small" onClick={() => setActive(record.record_id)}>Review</button></td></tr>)}</tbody></table>{!visibleRows.length && <p className="empty">No review records match this filter.</p>}</div>
    <div className="row-between" style={{marginTop: 12}}><span className="muted">Showing {rows.length ? (tablePage - 1) * 25 + 1 : 0}–{Math.min(tablePage * 25, rows.length)} of {rows.length} matching records</span><div className="actions"><button type="button" className="secondary small" disabled={tablePage === 1} onClick={() => setTablePage(value => value - 1)}>Previous</button><span>Page {tablePage} of {tablePages}</span><button type="button" className="secondary small" disabled={tablePage === tablePages} onClick={() => setTablePage(value => value + 1)}>Next</button></div></div>
    {activeRecord && <ReviewPanel record={activeRecord} masters={masters} onClose={() => setActive(undefined)} onUpdate={update} onValidate={validate} />}
  </section>;
}

function ReviewPanel({record, masters, onClose, onUpdate, onValidate}: {record: ReviewRecord; masters?: Masters; onClose: () => void; onUpdate: (id: string, change: (record: ReviewRecord) => ReviewRecord) => void; onValidate: (id: string) => void}) {
  const authors = record.draft.authors || [];
  const confirmedFaculty = authors.filter(author => record.contributors[String(author.author_order)]?.kind === "FACULTY");
  const editDraft = (values: Partial<Publication>, invalidate: (keyof ReviewRecord["confirmed_steps"])[] = []) => onUpdate(record.record_id, current => {
    const doiChanged = values.doi !== undefined && values.doi !== current.draft.doi;
    return {...current, draft: {...current.draft, ...values}, date_evidence: doiChanged ? undefined : current.date_evidence, manual_date: doiChanged ? undefined : current.manual_date, confirmed_steps: {...current.confirmed_steps, ...Object.fromEntries(invalidate.map(step => [step, "NOT_STARTED"]))}};
  });
  const chooseContributor = (author: Author, value: string) => onUpdate(record.record_id, current => {
    const [kind, id] = value.split(":");
    const contributors = {...current.contributors, [String(author.author_order)]: {kind: kind as ContributorDecision["kind"], person_id: id ? Number(id) : undefined, display_name: author.author_name_from_source}};
    const claimantStillValid = current.claiming_faculty_id && Object.values(contributors).some(decision => decision.kind === "FACULTY" && decision.person_id === current.claiming_faculty_id);
    return {...current, contributors, claiming_faculty_id: claimantStillValid ? current.claiming_faculty_id : undefined, confirmed_steps: {...current.confirmed_steps, contributors: "NOT_STARTED", claimant: "NOT_STARTED"}};
  });
  const evidence = dateSuggestion(record);
  return <section className="panel" role="dialog" aria-label={`Review ${record.source_title}`} style={{marginTop: 16}}><div className="row-between"><h3>Review: {record.source_title}</h3><button type="button" className="secondary" onClick={onClose}>Close review</button></div>
    <p className="muted">Source record {record.entry_number} · DOI {record.source_doi || "unavailable"} · Scopus EID {record.source_eid || "unmatched"}. Changing a DOI, classification, contributor, or claimant invalidates its related confirmation.</p>
    <div className="grid"><label className="field">Title<input value={record.draft.title || ""} onChange={event => editDraft({title: event.target.value}, ["metadata"])}/></label><label className="field">Publication type<select value={record.draft.publication_type || "OTHER"} onChange={event => editDraft({publication_type: event.target.value}, ["classification", "metadata"])}><option value="JOURNAL">Journal</option><option value="CONFERENCE">Conference</option><option value="OTHER">Policy review only</option></select></label><label className="field">Journal / proceedings title<input value={record.draft.journal_conference_name || record.draft.proceedings_title || ""} onChange={event => editDraft({journal_conference_name: event.target.value, proceedings_title: event.target.value}, ["metadata"])}/></label><label className="field">Conference name<input value={record.draft.conference_name || ""} onChange={event => editDraft({conference_name: event.target.value}, ["classification", "metadata"])} /></label><label className="field">Proposed publication date<input type="date" value={record.draft.publication_date || ""} onChange={event => onUpdate(record.record_id, current => ({...current, draft: {...current.draft, publication_date: event.target.value}, manual_date: current.manual_date ? {...current.manual_date, date: event.target.value} : undefined, confirmed_steps: {...current.confirmed_steps, date: "NOT_STARTED"}}))} /></label><label className="field">DOI<input value={record.draft.doi || ""} onChange={event => editDraft({doi: event.target.value}, ["date", "metadata"])} /></label><label className="field">Publisher<input value={record.draft.publisher || ""} onChange={event => editDraft({publisher: event.target.value}, ["metadata"])}/></label><label className="field">Volume<input value={record.draft.volume || ""} onChange={event => editDraft({volume: event.target.value}, ["metadata"])} /></label><label className="field">Issue<input value={record.draft.issue || ""} onChange={event => editDraft({issue: event.target.value}, ["metadata"])} /></label><label className="field">Pages / article number<input value={record.draft.pages_or_article_number || ""} onChange={event => editDraft({pages_or_article_number: event.target.value}, ["metadata"])} /></label><label className="field">ISSN<input value={record.draft.issn || ""} onChange={event => editDraft({issn: event.target.value}, ["metadata"])} /></label><label className="field">ISBN<input value={record.draft.isbn || ""} onChange={event => editDraft({isbn: event.target.value}, ["metadata"])} /></label></div>
    <details><summary>Original source metadata and review proposal</summary><div className="table-wrap"><table><thead><tr><th>Field</th><th>Original source value</th><th>Reviewer proposal</th></tr></thead><tbody>{[["Title", record.original.title, record.draft.title], ["DOI", record.original.doi, record.draft.doi], ["Venue", record.original.journal_conference_name || record.original.proceedings_title, record.draft.journal_conference_name || record.draft.proceedings_title], ["Date", record.original.publication_date, record.draft.publication_date], ["Publisher", record.original.publisher, record.draft.publisher]].map(([field, original, proposed]) => <tr key={String(field)}><td>{field}</td><td>{original || "—"}</td><td>{proposed || "—"}</td></tr>)}</tbody></table></div></details>
    {evidence && <div className="notice"><strong>Date evidence</strong><p>{evidence.date} · {evidence.precision} · {evidence.date_type} · {evidence.source}</p><a href={evidence.source_url} target="_blank" rel="noreferrer">Open source evidence</a>{evidence.precision === "DAY" && <button type="button" className="secondary small" onClick={() => editDraft({publication_date: evidence.date}, ["date"])}>Use this exact date as proposal</button>}</div>}
    <div className="grid"><label className="field">Manual date evidence source<input value={record.manual_date?.evidence || ""} onChange={event => onUpdate(record.record_id, current => ({...current, manual_date: {...current.manual_date, date: current.draft.publication_date || "", evidence: event.target.value, date_type: current.manual_date?.date_type || "PUBLISHED_ONLINE"}, confirmed_steps: {...current.confirmed_steps, date: "NOT_STARTED"}}))} placeholder="Publisher page or document reference"/></label><label className="field">Manual date type<select value={record.manual_date?.date_type || "PUBLISHED_ONLINE"} onChange={event => onUpdate(record.record_id, current => ({...current, manual_date: {...current.manual_date, date: current.draft.publication_date || "", evidence: current.manual_date?.evidence || "", date_type: event.target.value}, confirmed_steps: {...current.confirmed_steps, date: "NOT_STARTED"}}))}><option value="PUBLISHED_ONLINE">Published online</option><option value="PUBLISHED_PRINT">Published in print</option><option value="OTHER">Other verified publication date</option></select></label><label className="field">Explanation if different from provider metadata<input value={record.manual_date?.explanation || ""} onChange={event => onUpdate(record.record_id, current => ({...current, manual_date: {...current.manual_date, date: current.draft.publication_date || "", evidence: current.manual_date?.evidence || "", date_type: current.manual_date?.date_type || "PUBLISHED_ONLINE", explanation: event.target.value}, confirmed_steps: {...current.confirmed_steps, date: "NOT_STARTED"}}))}/></label></div>
    <h4>Contributor reconciliation</h4><div className="table-wrap"><table><thead><tr><th>Order</th><th>Source author</th><th>Match evidence</th><th>Reviewer assignment</th></tr></thead><tbody>{authors.map(author => { const decision = record.contributors[String(author.author_order)] || {kind: "UNRESOLVED"}; return <tr key={author.author_order}><td>{author.author_order}</td><td>{author.author_name_from_source}</td><td>{author.matching_status}{author.matching_confidence != null ? ` · ${Math.round(author.matching_confidence * 100)}%` : ""}</td><td><select aria-label={`Contributor ${author.author_order}`} value={`${decision.kind}:${decision.person_id || ""}`} onChange={event => chooseContributor(author, event.target.value)}><option value="UNRESOLVED:">Unresolved</option><option value="EXTERNAL:">External author</option>{masters?.faculty.filter(person => person.is_active).map(person => <option value={`FACULTY:${person.id}`} key={`f${person.id}`}>Faculty · {person.name} ({person.employee_id || person.id}){person.department ? ` · ${person.department.code}` : ""}</option>)}{masters?.students.filter(person => person.is_active).map(person => <option value={`STUDENT:${person.id}`} key={`s${person.id}`}>Student · {person.name} ({person.roll_number || person.id})</option>)}</select></td></tr>; })}</tbody></table></div>
    <label className="field">Claiming Faculty<select aria-label="Claiming Faculty for review" value={record.claiming_faculty_id || ""} onChange={event => onUpdate(record.record_id, current => ({...current, claiming_faculty_id: event.target.value ? Number(event.target.value) : undefined, confirmed_steps: {...current.confirmed_steps, claimant: "NOT_STARTED"}}))}><option value="">Select exactly one confirmed Faculty</option>{confirmedFaculty.map(author => { const id = record.contributors[String(author.author_order)]?.person_id; const person = masters?.faculty.find(item => item.id === id); return id ? <option key={id} value={id}>{person?.name || author.author_name_from_source}</option> : null; })}</select></label>
    <h4>Review confirmations</h4><div className="actions">{STEPS.map(step => <label className="check" key={step}><input type="checkbox" checked={record.confirmed_steps[step] === "CONFIRMED"} onChange={event => onUpdate(record.record_id, current => ({...current, confirmed_steps: {...current.confirmed_steps, [step]: event.target.checked ? "CONFIRMED" : "NOT_STARTED"}}))}/>{step}</label>)}</div>
    {record.warnings.length > 0 && <ul className="error">{record.warnings.map(warning => <li key={warning}>{warning}</li>)}</ul>}
    <div className="actions"><button type="button" disabled={record.review_status !== "READY_FOR_FINAL_VALIDATION"} onClick={() => onValidate(record.record_id)}>Validate for Stage 2B</button><span className="badge">{record.review_status}</span></div>
  </section>;
}
