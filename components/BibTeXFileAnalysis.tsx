"use client";

import {ChangeEvent, useMemo, useRef, useState} from "react";
import Link from "next/link";
import {api, ApiError, Author, Publication} from "@/lib/api";

type Match = {publication_id?: number; entry_number?: number; citation_key?: string | null; title?: string; doi?: string | null; is_active?: boolean; reason?: string};
type DateSuggestion = {date: string; precision: "YEAR" | "MONTH" | "DAY"; date_type: string; source_field: string; is_exact_online?: boolean};
type Enrichment = {entry_number: number; doi: string; status: string; source?: string; preferred?: DateSuggestion | null; alternatives?: DateSuggestion[]; error?: string; provider_title?: string | null; identity_conflicts?: {field: string; bibtex_value: string; provider_value: string; assessment: string}[]; bibtex_date_conflict?: boolean};
type CsvRecord = {source_row: number; eid: string; doi?: string | null; title: string; year: string; document_type: string; source_title?: string; conference_name?: string; warnings?: string[]};
type Draft = Partial<Publication> & {authors?: Author[]; raw_metadata_json?: Record<string, unknown>};
type AnalysisEntry = {
  entry_number: number; citation_key?: string | null; raw_bibtex?: string; errors: string[]; warnings: string[];
  publication?: Draft; publication_year?: string | null; primary_disposition: string; missing_metadata: string[];
  duplicate_matches: {database_exact: Match[]; within_file_exact: Match[]; database_possible: Match[]; within_file_possible: Match[]};
  repeated_citation_keys: Match[]; duplicate_status: string; metadata_status: string; publication_date_status: string; import_eligibility: string;
  document_classification?: {bibtex_type?: string; scopus_document_type?: string | null; suggested_module?: string; classification_conflict?: boolean; special_record?: boolean};
  scopus_match?: {status: string; matches: (CsvRecord & {match_method?: string; ambiguity_reason?: string; source_conflicts?: SourceConflict[]})[]; candidate_entry_numbers?: number[]; csv_record?: CsvRecord | null; matching_evidence?: {method?: string | null; candidate_csv_rows?: number[]; candidate_scopus_eids?: string[]; ambiguity_reason?: string | null}};
  source_conflicts?: SourceConflict[];
  date_enrichment?: Enrichment;
};
type SourceConflict = {field: string; bibtex_value?: string | null; scopus_value?: string | null; assessment: string; severity: string};
type ScopusAnalysis = {records: CsvRecord[]; unmatched_records: (CsvRecord & {match_status: string; candidate_entry_numbers?: number[]})[]; summary: Record<string, number>};
type Analysis = {
  analysis_only: true; file_name: string; file_size_bytes: number; scopus_file_name?: string; total_entries: number; entries: AnalysisEntry[]; scopus?: ScopusAnalysis;
  summary: {total_entries: number; successfully_parsed: number; parse_errors: number; unsupported_types: number; exact_matches_already_in_database: number; new_candidates: number; needs_metadata_review: number; review_dimensions?: {duplicate_statuses: Record<string, number>; metadata_statuses: Record<string, number>; date_statuses: Record<string, number>; document_modules: Record<string, number>; missing_exact_publication_dates: number; missing_venues: number; valid_dois: number; missing_dois: number; no_duplicate_detected: number; potentially_new_needs_review: number}};
};

const PRIMARY_FILTERS = [["ALL", "All primary results"], ["POTENTIALLY_NEW_NEEDS_REVIEW", "Potentially new — needs review"], ["NEW_CANDIDATE", "New candidates"], ["ALREADY_IN_DATABASE", "Already in database"], ["DUPLICATE_WITHIN_FILE", "Duplicate within BibTeX"], ["POSSIBLE_DUPLICATE", "Possible duplicate"], ["NEEDS_METADATA_REVIEW", "Needs metadata review"], ["PARSE_ERROR", "Parse errors"], ["UNSUPPORTED_TYPE", "Unsupported types"]] as const;
const PAGE_SIZE = 25;
const display = (value: string | null | undefined) => value || "—";
const friendly = (value: string | null | undefined) => display(value?.toLowerCase().replaceAll("_", " ").replace(/\b\w/g, character => character.toUpperCase()));
const authorNames = (authors: Author[] | undefined) => authors?.map(author => author.author_name_from_source).filter(Boolean).join("; ") || "—";

function duplicateMatches(entry: AnalysisEntry) {
  return [...entry.duplicate_matches.database_exact, ...entry.duplicate_matches.within_file_exact, ...entry.duplicate_matches.database_possible, ...entry.duplicate_matches.within_file_possible];
}

export default function BibTeXFileAnalysis() {
  const bibInputRef = useRef<HTMLInputElement>(null);
  const csvInputRef = useRef<HTMLInputElement>(null);
  const requestRef = useRef<AbortController | null>(null);
  const enrichmentRef = useRef<AbortController | null>(null);
  const [bibFile, setBibFile] = useState<File>();
  const [scopusFile, setScopusFile] = useState<File>();
  const [analysis, setAnalysis] = useState<Analysis>();
  const [busy, setBusy] = useState(false);
  const [enriching, setEnriching] = useState(false);
  const [error, setError] = useState("");
  const [primaryFilter, setPrimaryFilter] = useState("ALL");
  const [duplicateFilter, setDuplicateFilter] = useState("ALL");
  const [metadataFilter, setMetadataFilter] = useState("ALL");
  const [sourceFilter, setSourceFilter] = useState("ALL");
  const [documentFilter, setDocumentFilter] = useState("ALL");
  const [conflictFilter, setConflictFilter] = useState("ALL");
  const [dateFilter, setDateFilter] = useState("ALL");
  const [enrichmentFilter, setEnrichmentFilter] = useState("ALL");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("SOURCE");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<AnalysisEntry>();

  function resetTable() {
    setPrimaryFilter("ALL"); setDuplicateFilter("ALL"); setMetadataFilter("ALL"); setSourceFilter("ALL"); setDocumentFilter("ALL"); setConflictFilter("ALL"); setDateFilter("ALL"); setEnrichmentFilter("ALL");
    setQuery(""); setSort("SOURCE"); setPage(1); setSelected(undefined);
  }
  function selectBibFile(event: ChangeEvent<HTMLInputElement>) {
    requestRef.current?.abort(); enrichmentRef.current?.abort(); setBibFile(event.target.files?.[0]); setAnalysis(undefined); setError(""); resetTable();
  }
  function selectScopusFile(event: ChangeEvent<HTMLInputElement>) {
    requestRef.current?.abort(); enrichmentRef.current?.abort(); setScopusFile(event.target.files?.[0]); setAnalysis(undefined); setError(""); resetTable();
  }
  function clear() {
    requestRef.current?.abort(); enrichmentRef.current?.abort(); setBibFile(undefined); setScopusFile(undefined); setAnalysis(undefined); setError(""); resetTable();
    if (bibInputRef.current) bibInputRef.current.value = "";
    if (csvInputRef.current) csvInputRef.current.value = "";
  }
  async function analyze() {
    if (!bibFile || busy) return;
    const controller = new AbortController(); requestRef.current = controller;
    setBusy(true); setError(""); setAnalysis(undefined); resetTable();
    const form = new FormData(); form.append("file", bibFile);
    if (scopusFile) form.append("scopus_file", scopusFile);
    try {
      setAnalysis(await api<Analysis>("/publications/analyze-bibtex-file", {method: "POST", body: form, signal: controller.signal}));
    } catch (cause) {
      if ((cause as Error).name !== "AbortError") setError((cause as ApiError).message || "The files could not be analyzed.");
    } finally {
      if (requestRef.current === controller) requestRef.current = null;
      setBusy(false);
    }
  }
  const filtered = useMemo(() => {
    if (!analysis) return [];
    const search = query.trim().toLocaleLowerCase();
    const values = analysis.entries.filter(entry =>
      (primaryFilter === "ALL" || entry.primary_disposition === primaryFilter || (primaryFilter === "POTENTIALLY_NEW_NEEDS_REVIEW" && entry.duplicate_status === "NO_DUPLICATE_DETECTED" && entry.metadata_status === "NEEDS_REVIEW")) &&
      (duplicateFilter === "ALL" || entry.duplicate_status === duplicateFilter) &&
      (metadataFilter === "ALL" || entry.metadata_status === metadataFilter) &&
      (sourceFilter === "ALL" || entry.scopus_match?.status === sourceFilter) &&
      (documentFilter === "ALL" || entry.document_classification?.suggested_module === documentFilter) &&
      (conflictFilter === "ALL" || (conflictFilter === "HAS_CONFLICT" ? Boolean(entry.source_conflicts?.length) : !entry.source_conflicts?.length)) &&
      (dateFilter === "ALL" || (dateFilter === "MISSING" ? entry.publication_date_status === "MISSING" : entry.publication_date_status !== "MISSING")) &&
      (enrichmentFilter === "ALL" || entry.date_enrichment?.status === enrichmentFilter) &&
      (!search || [entry.citation_key, entry.publication?.title, entry.publication?.doi, entry.publication_year, authorNames(entry.publication?.authors), entry.document_classification?.scopus_document_type].join(" ").toLocaleLowerCase().includes(search))
    );
    return values.sort((left, right) => sort === "TITLE" ? (left.publication?.title || "").localeCompare(right.publication?.title || "") : sort === "YEAR" ? (right.publication_year || "").localeCompare(left.publication_year || "") : sort === "DISPOSITION" ? left.primary_disposition.localeCompare(right.primary_disposition) : left.entry_number - right.entry_number);
  }, [analysis, primaryFilter, duplicateFilter, metadataFilter, sourceFilter, documentFilter, conflictFilter, dateFilter, enrichmentFilter, query, sort]);
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const eligibleForDateLookup = analysis?.entries.filter(entry => Boolean(entry.publication?.doi) && entry.publication_date_status === "MISSING" && entry.duplicate_status !== "EXISTING_DATABASE" && entry.scopus_match?.status !== "AMBIGUOUS").slice(0, 25) || [];

  async function enrichDates() {
    if (!eligibleForDateLookup.length || enriching) return;
    const controller = new AbortController(); enrichmentRef.current = controller;
    setEnriching(true); setError("");
    try {
      const result = await api<{results: Enrichment[]}>("/publications/analyze-bibtex-file/enrich-dates", {
        method: "POST", signal: controller.signal, body: JSON.stringify({entries: eligibleForDateLookup.map(entry => ({entry_number: entry.entry_number, doi: entry.publication?.doi, title: entry.publication?.title, publication_year: entry.publication_year, bibtex_date: entry.publication?.publication_date}))}),
      });
      const byNumber = new Map(result.results.map(item => [item.entry_number, item]));
      setAnalysis(current => current ? {...current, entries: current.entries.map(entry => {
        const date_enrichment = byNumber.get(entry.entry_number);
        return date_enrichment ? {...entry, date_enrichment, publication_date_status: date_enrichment.preferred ? "DOI_SUGGESTION_AVAILABLE" : entry.publication_date_status} : entry;
      })} : current);
    } catch (cause) {if ((cause as Error).name !== "AbortError") setError((cause as ApiError).message || "Date enrichment could not be completed.");}
    finally {if (enrichmentRef.current === controller) enrichmentRef.current = null; setEnriching(false);}
  }

  function cancelEnrichment() {enrichmentRef.current?.abort();}

  return <section className="panel" aria-label="Upload BibTeX File">
    <div className="step">Analysis-only upload</div><h2>Upload BibTeX File</h2>
    <p className="muted">Review a UTF-8 <code>.bib</code> export on its own, or reconcile it with an optional Scopus CSV. Neither source is stored and no publication, author, claimant, evidence, or master record is saved.</p>
    <div className="grid">
      <label className="field" htmlFor="bibtex-analysis-file">BibTeX file<input ref={bibInputRef} id="bibtex-analysis-file" type="file" accept=".bib,application/x-bibtex,text/x-bibtex" onChange={selectBibFile} disabled={busy}/></label>
      <label className="field" htmlFor="scopus-analysis-file">Scopus CSV file (optional)<input ref={csvInputRef} id="scopus-analysis-file" type="file" accept=".csv,text/csv" onChange={selectScopusFile} disabled={busy}/></label>
    </div>
    <div className="actions" style={{marginTop: 12}}><button type="button" onClick={analyze} disabled={!bibFile || busy}>{busy ? "Analyzing…" : scopusFile ? "Analyze BibTeX + Scopus CSV" : "Analyze BibTeX File"}</button>{(bibFile || scopusFile || analysis) && <button type="button" className="secondary" onClick={clear} disabled={busy || enriching}>Clear analysis</button>}</div>
    {busy && <p role="status">Analyzing uploaded source data and checking existing publications without saving anything…</p>}
    {error && <div className="error" role="alert">{error}</div>}
    {analysis && <>
      <div className="notice" role="status"><strong>Analysis Only — No Publications Have Been Saved</strong><p>{analysis.file_name} · {analysis.total_entries} entries detected · {(analysis.file_size_bytes / 1024).toFixed(1)} KB{analysis.scopus_file_name ? ` · ${analysis.scopus_file_name} matched as source metadata only.` : ""}</p></div>
      <div className="analysis-summary" aria-label="BibTeX and Scopus analysis summary">
        <section><h3>Source reconciliation</h3><div className="analysis-summary-cards">{[["BibTeX entries", analysis.total_entries], ["CSV records", analysis.scopus?.summary.total_csv_records], ["Unique CSV matches", analysis.scopus?.summary.unique_csv_matches], ["Ambiguous CSV", analysis.scopus?.summary.ambiguous_csv_records], ["BibTeX-only", analysis.scopus?.summary.bibtex_only_entries], ["CSV-only", analysis.scopus?.summary.csv_only_records], ["Entries with conflicts", analysis.scopus?.summary.entries_with_source_conflicts]].filter(([, value]) => value !== undefined).map(([label, value]) => <div className="analysis-card" key={String(label)}><span>{label}</span><strong>{value}</strong></div>)}</div></section>
        <section><h3>Duplicate detection</h3><div className="analysis-summary-cards">{[["Existing database", analysis.summary.review_dimensions?.duplicate_statuses.EXISTING_DATABASE], ["Duplicate upload", analysis.summary.review_dimensions?.duplicate_statuses.DUPLICATE_WITHIN_UPLOAD], ["Possible duplicate", analysis.summary.review_dimensions?.duplicate_statuses.POSSIBLE_DUPLICATE], ["No duplicate detected", analysis.summary.review_dimensions?.no_duplicate_detected]].map(([label, value]) => <div className="analysis-card" key={String(label)}><span>{label}</span><strong>{value ?? 0}</strong></div>)}</div></section>
        <section><h3>Metadata quality</h3><div className="analysis-summary-cards">{[["Missing exact dates", analysis.summary.review_dimensions?.missing_exact_publication_dates], ["Missing venues", analysis.summary.review_dimensions?.missing_venues], ["Valid DOI", analysis.summary.review_dimensions?.valid_dois], ["Missing DOI", analysis.summary.review_dimensions?.missing_dois], ["Metadata complete", analysis.summary.review_dimensions?.metadata_statuses.COMPLETE], ["Potentially new — needs review", analysis.summary.review_dimensions?.potentially_new_needs_review]].map(([label, value]) => <div className="analysis-card" key={String(label)}><span>{label}</span><strong>{value ?? 0}</strong></div>)}</div></section>
        {analysis.scopus && <section><h3>Document classification</h3><div className="analysis-summary-cards">{[["Journal candidates", analysis.summary.review_dimensions?.document_modules.JOURNAL], ["Conference candidates", analysis.summary.review_dimensions?.document_modules.CONFERENCE], ["Books / Chapters", analysis.summary.review_dimensions?.document_modules.BOOKS_CHAPTERS], ["Special records", analysis.summary.review_dimensions?.document_modules.SPECIAL], ["Document-type conflicts", analysis.scopus.summary.classification_conflicts]].map(([label, value]) => <div className="analysis-card" key={String(label)}><span>{label}</span><strong>{value ?? 0}</strong></div>)}</div></section>}
        <section><h3>DOI enrichment</h3><div className="analysis-summary-cards">{[["Eligible records", eligibleForDateLookup.length], ["Requested", analysis.entries.filter(entry => Boolean(entry.date_enrichment)).length], ["Exact online dates", analysis.entries.filter(entry => entry.date_enrichment?.preferred?.is_exact_online).length], ["Alternative dates", analysis.entries.filter(entry => (entry.date_enrichment?.alternatives?.length || 0) > 1).length], ["Partial dates", analysis.entries.filter(entry => entry.date_enrichment?.preferred && entry.date_enrichment.preferred.precision !== "DAY").length], ["Provider failures", analysis.entries.filter(entry => entry.date_enrichment?.status === "UNAVAILABLE").length], ["Identity conflicts", analysis.entries.filter(entry => entry.date_enrichment?.status === "IDENTITY_CONFLICT").length]].map(([label, value]) => <div className="analysis-card" key={String(label)}><span>{label}</span><strong>{value}</strong></div>)}</div></section>
      </div>
      {eligibleForDateLookup.length > 0 && <div className="notice" style={{marginTop: 16}}><strong>Optional DOI date enrichment</strong><p>Up to {eligibleForDateLookup.length} eligible DOI rows have no exact BibTeX date. Crossref suggestions identify date type and precision, require review, and never update records.</p><div className="actions"><button type="button" className="secondary" onClick={enrichDates} disabled={enriching}>{enriching ? "Requesting date suggestions…" : "Enrich Publication Dates from DOI"}</button>{enriching && <button type="button" className="secondary" onClick={cancelEnrichment}>Cancel request</button>}</div></div>}
      <div className="grid" style={{marginTop: 20}}>
        <label className="field">Find entries<input value={query} onChange={event => {setQuery(event.target.value); setPage(1);}} placeholder="Title, DOI, citation key, author or Scopus type"/></label>
        <label className="field">Primary review<select value={primaryFilter} onChange={event => {setPrimaryFilter(event.target.value); setPage(1);}}>{PRIMARY_FILTERS.map(([value, name]) => <option value={value} key={value}>{name}</option>)}</select></label>
        <label className="field">Duplicate status<select value={duplicateFilter} onChange={event => {setDuplicateFilter(event.target.value); setPage(1);}}><option value="ALL">All duplicate statuses</option>{["EXISTING_DATABASE", "DUPLICATE_WITHIN_UPLOAD", "POSSIBLE_DUPLICATE", "NO_DUPLICATE_DETECTED", "UNDETERMINED"].map(value => <option key={value} value={value}>{friendly(value)}</option>)}</select></label>
        <label className="field">Metadata readiness<select value={metadataFilter} onChange={event => {setMetadataFilter(event.target.value); setPage(1);}}><option value="ALL">All metadata states</option>{["COMPLETE", "NEEDS_REVIEW", "UNSUPPORTED", "PARSE_ERROR"].map(value => <option key={value} value={value}>{friendly(value)}</option>)}</select></label>
        {analysis.scopus && <label className="field">Scopus reconciliation<select value={sourceFilter} onChange={event => {setSourceFilter(event.target.value); setPage(1);}}><option value="ALL">All source matches</option>{["MATCHED", "AMBIGUOUS", "BIBTEX_ONLY", "CONFLICT"].map(value => <option key={value} value={value}>{friendly(value)}</option>)}</select></label>}
        <label className="field">Document type<select value={documentFilter} onChange={event => {setDocumentFilter(event.target.value); setPage(1);}}><option value="ALL">All suggested modules</option>{["JOURNAL", "CONFERENCE", "BOOKS_CHAPTERS", "SPECIAL", "POLICY_REVIEW"].map(value => <option key={value} value={value}>{friendly(value)}</option>)}</select></label>
        {analysis.scopus && <label className="field">Source conflict<select value={conflictFilter} onChange={event => {setConflictFilter(event.target.value); setPage(1);}}><option value="ALL">All source comparisons</option><option value="HAS_CONFLICT">Has source conflict</option><option value="NO_CONFLICT">No source conflict</option></select></label>}
        <label className="field">Publication date<select value={dateFilter} onChange={event => {setDateFilter(event.target.value); setPage(1);}}><option value="ALL">All date states</option><option value="MISSING">Missing exact date</option><option value="PRESENT">Exact or suggested date</option></select></label>
        <label className="field">DOI enrichment<select value={enrichmentFilter} onChange={event => {setEnrichmentFilter(event.target.value); setPage(1);}}><option value="ALL">All enrichment states</option><option value="FOUND">Date suggestion found</option><option value="IDENTITY_CONFLICT">Identity conflict</option><option value="UNAVAILABLE">Provider unavailable</option></select></label>
        <label className="field">Sort entries<select value={sort} onChange={event => {setSort(event.target.value); setPage(1);}}><option value="SOURCE">Original source order</option><option value="TITLE">Title</option><option value="YEAR">Publication year</option><option value="DISPOSITION">Primary review result</option></select></label>
      </div>
      <div className="table-wrap" style={{marginTop: 16}}><table className="analysis-review-table"><thead><tr>{["#", "Publication title", "Year", "Document type", "Suggested module", "DOI", "Duplicate", "Metadata", "Date", "Source match", "Review"].map(heading => <th key={heading}>{heading}</th>)}</tr></thead><tbody>{visible.map(entry => <tr key={entry.entry_number}><td>{entry.entry_number}</td><td className="analysis-title" title={entry.publication?.title || ""}>{display(entry.publication?.title)}<small>{display(entry.citation_key)}</small></td><td>{display(entry.publication_year)}</td><td>{display(entry.document_classification?.bibtex_type)}{entry.document_classification?.scopus_document_type ? <small>{entry.document_classification.scopus_document_type}</small> : ""}</td><td>{friendly(entry.document_classification?.suggested_module)}</td><td className="analysis-doi" title={entry.publication?.doi || ""}>{display(entry.publication?.doi)}</td><td><span className="badge">{friendly(entry.duplicate_status)}</span></td><td><span className="badge">{friendly(entry.metadata_status)}</span></td><td><span className="badge">{friendly(entry.publication_date_status)}</span></td><td><span className="badge">{friendly(entry.scopus_match?.status || "BIBTEX_ONLY")}</span>{entry.source_conflicts?.length ? <small>{entry.source_conflicts.length} conflict{entry.source_conflicts.length === 1 ? "" : "s"}</small> : ""}</td><td><button type="button" className="secondary small" onClick={() => setSelected(entry)}>Review</button></td></tr>)}</tbody></table>{!visible.length && <p className="empty">No entries match this analysis filter.</p>}</div>
      <div className="row-between" style={{marginTop: 16}}><span className="muted">Showing {filtered.length ? (page - 1) * PAGE_SIZE + 1 : 0}–{Math.min(page * PAGE_SIZE, filtered.length)} of {filtered.length} matching entries</span><div className="actions"><button type="button" className="secondary small" disabled={page === 1} onClick={() => setPage(value => value - 1)}>Previous</button><span>Page {page} of {totalPages}</span><button type="button" className="secondary small" disabled={page === totalPages} onClick={() => setPage(value => value + 1)}>Next</button></div></div>
      {analysis.scopus && analysis.scopus.unmatched_records.length > 0 && <section className="panel" style={{marginTop: 20}}><h3>Scopus-only or ambiguous source records</h3><p className="muted">These are CSV source rows requiring manual review. They are not added to any publication queue.</p><div className="table-wrap"><table><thead><tr><th>CSV row</th><th>EID</th><th>Title</th><th>Year</th><th>DOI</th><th>Result</th></tr></thead><tbody>{analysis.scopus.unmatched_records.map(record => <tr key={record.source_row}><td>{record.source_row}</td><td>{display(record.eid)}</td><td>{display(record.title)}</td><td>{display(record.year)}</td><td>{display(record.doi)}</td><td>{friendly(record.match_status)}</td></tr>)}</tbody></table></div></section>}
      {selected && <section className="panel" role="dialog" aria-label={`BibTeX entry ${selected.entry_number} details`} style={{marginTop: 20}}><div className="row-between"><h2>Entry {selected.entry_number} · {display(selected.citation_key)}</h2><button type="button" className="secondary" onClick={() => setSelected(undefined)}>Close details</button></div><p><span className="badge">{friendly(selected.primary_disposition)}</span></p><h3>Independent review dimensions</h3><p>Duplicate: <strong>{friendly(selected.duplicate_status)}</strong> · Metadata: <strong>{friendly(selected.metadata_status)}</strong> · Eligibility: <strong>{friendly(selected.import_eligibility)}</strong></p><p>Document: BibTeX <strong>{display(selected.document_classification?.bibtex_type)}</strong>{selected.document_classification?.scopus_document_type ? <> · Scopus <strong>{selected.document_classification.scopus_document_type}</strong></> : ""} · Suggested module: <strong>{friendly(selected.document_classification?.suggested_module)}</strong></p>{selected.document_classification?.classification_conflict && <p className="error">The BibTeX and Scopus document classifications conflict; resolve manually.</p>}
        <h3>Publication identity</h3><dl className="detail-grid"><div><dt>Title</dt><dd>{display(selected.publication?.title)}</dd></div><div><dt>DOI</dt><dd>{display(selected.publication?.doi)}</dd></div><div><dt>Year</dt><dd>{display(selected.publication_year)}</dd></div><div><dt>Citation key</dt><dd>{display(selected.citation_key)}</dd></div><div><dt>Scopus EID</dt><dd>{display(selected.scopus_match?.csv_record?.eid)}</dd></div><div><dt>Source match</dt><dd>{friendly(selected.scopus_match?.status || "BIBTEX_ONLY")}</dd></div></dl>
        <h3>Duplicate analysis</h3><ul>{duplicateMatches(selected).map((match, index) => <li key={`${match.publication_id || match.entry_number}-${index}`}>{match.publication_id ? <>Database publication <Link href={`/publications/${match.publication_id}`}>#{match.publication_id}{match.is_active === false ? " (inactive)" : ""}</Link> · {display(match.title || match.doi)}</> : <>BibTeX entry {match.entry_number} · {display(match.citation_key)} · {display(match.reason)}</>}</li>)}{!duplicateMatches(selected).length && <li>No duplicate match detected.</li>}</ul>
        {selected.repeated_citation_keys.length > 0 && <p className="muted">The citation key is also used by BibTeX entry {selected.repeated_citation_keys.map(match => match.entry_number).join(", ")}. Citation keys are review metadata, not publication identifiers.</p>}
        <h3>Source reconciliation</h3>{selected.scopus_match?.csv_record ? <p>Matched Scopus CSV row {selected.scopus_match.csv_record.source_row} ({display(selected.scopus_match.csv_record.eid)}) by {selected.scopus_match.matching_evidence?.method || "review"}. CSV title: {display(selected.scopus_match.csv_record.title)}.</p> : <p>{selected.scopus_match?.matching_evidence?.ambiguity_reason ? `No unique source match: ${friendly(selected.scopus_match.matching_evidence.ambiguity_reason)}. Candidate CSV rows: ${selected.scopus_match.matching_evidence.candidate_csv_rows?.join(", ") || "—"}.` : "No CSV candidate was identified for this BibTeX entry."}</p>}
        {selected.source_conflicts && selected.source_conflicts.length > 0 && <><h3>Source differences</h3><div className="table-wrap"><table><thead><tr><th>Field</th><th>BibTeX</th><th>Scopus CSV</th><th>Assessment</th></tr></thead><tbody>{selected.source_conflicts.map((conflict, index) => <tr key={`${conflict.field}-${index}`}><td>{conflict.field}</td><td>{display(conflict.bibtex_value)}</td><td>{display(conflict.scopus_value)}</td><td><span className="badge">{friendly(conflict.severity)}</span>{conflict.assessment}</td></tr>)}</tbody></table></div></>}
        <h3>Publication date review</h3>{selected.date_enrichment ? <><p>{["FOUND", "IDENTITY_CONFLICT"].includes(selected.date_enrichment.status) && selected.date_enrichment.preferred ? <>Suggested {selected.date_enrichment.preferred.date} ({selected.date_enrichment.preferred.precision}, {selected.date_enrichment.preferred.date_type}{selected.date_enrichment.preferred.is_exact_online ? ", exact online date" : ""}) from Crossref. This is a review suggestion only.</> : selected.date_enrichment.error || "No Crossref date suggestion is available."}</p>{selected.date_enrichment.bibtex_date_conflict && <p className="error">The preferred Crossref date differs from the original BibTeX date. Both values are preserved for manual verification.</p>}{selected.date_enrichment.identity_conflicts?.length ? <p className="error">Provider identity differs: {selected.date_enrichment.identity_conflicts.map(conflict => conflict.field).join(", ")}. Do not treat the date as verified.</p> : null}{selected.date_enrichment.alternatives && selected.date_enrichment.alternatives.length > 1 && <ul>{selected.date_enrichment.alternatives.slice(1).map(item => <li key={`${item.source_field}-${item.date}`}>{item.date} · {item.precision} · {item.date_type}</li>)}</ul>}</> : <p>{selected.publication?.publication_date ? `BibTeX exact date: ${selected.publication.publication_date}` : "No exact BibTeX date. Optional DOI enrichment may be available."}</p>}
        <h3>Metadata and authors</h3><p>{selected.missing_metadata.length ? `Missing: ${selected.missing_metadata.join(", ")}` : "No required metadata gaps detected by analysis."}</p><p>{authorNames(selected.publication?.authors)}</p><h3>Original BibTeX</h3><pre className="raw-bibtex">{selected.raw_bibtex || "No recoverable raw BibTeX is available for this parse error."}</pre>
      </section>}
    </>}
  </section>;
}
