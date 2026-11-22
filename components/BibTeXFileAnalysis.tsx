"use client";

import {ChangeEvent, MouseEvent, useMemo, useRef, useState} from "react";
import Link from "next/link";
import {api, ApiError, Author, Publication} from "@/lib/api";
import BulkPublicationReviewWorkspace from "@/components/BulkPublicationReviewWorkspace";

type Match = {publication_id?: number; entry_number?: number; citation_key?: string | null; title?: string; doi?: string | null; is_active?: boolean; reason?: string; claiming_faculty?: {faculty_id: number; name: string} | null};
type DateSuggestion = {date: string; precision: "YEAR" | "MONTH" | "DAY"; date_type: string; source_field: string; is_exact_online?: boolean};
type VerificationCandidate = {date: string; precision: string; date_type: string; source: string; source_field: string; source_url: string; assessment: string};
type Verification = {identity_status: string; candidates: VerificationCandidate[]; suggested_date?: VerificationCandidate | null; suggestion_status: string; requires_review: boolean; provider_failures: {source: string; error: string}[]; bibtex_date_conflict?: boolean};
type Enrichment = {entry_number: number; doi: string; status: string; source?: string; preferred?: DateSuggestion | null; alternatives?: DateSuggestion[]; error?: string; bibtex_date_conflict?: boolean; verification?: Verification};
type ImportReadiness = {status: string; blockers: string[]; warnings: string[]; explanations: Record<string, string>; contributors: {source_authors: number; matched_faculty: number; matched_students: number; unresolved_internal: number; external_or_unmatched: number}; claimant_candidates: {faculty_id: number; name: string; confidence?: number | null; matching_status?: string; department?: {id: number; code: string; name: string} | null}[]};
type CsvRecord = {source_row: number; eid: string; doi?: string | null; title: string; year: string; document_type: string; source_title?: string; conference_name?: string; conference_date?: string; conference_location?: string; publisher?: string; volume?: string; isbn?: string; issn?: string; warnings?: string[]};
type Draft = Partial<Publication> & {authors?: Author[]; raw_metadata_json?: Record<string, unknown>};
type AnalysisEntry = {
  entry_number: number; citation_key?: string | null; raw_bibtex?: string; errors: string[]; warnings: string[];
  publication?: Draft; publication_year?: string | null; primary_disposition: string; missing_metadata: string[];
  duplicate_matches: {database_exact: Match[]; within_file_exact: Match[]; database_possible: Match[]; within_file_possible: Match[]};
  repeated_citation_keys: Match[]; duplicate_status: string; metadata_status: string; publication_date_status: string; import_eligibility: string;
  document_classification?: {bibtex_type?: string; scopus_document_type?: string | null; suggested_module?: string; classification_conflict?: boolean; special_record?: boolean};
  scopus_match?: {status: string; metadata_comparison?: string; matches: (CsvRecord & {match_method?: string; ambiguity_reason?: string; source_conflicts?: SourceConflict[]})[]; candidate_entry_numbers?: number[]; csv_record?: CsvRecord | null; matching_evidence?: {method?: string | null; candidate_csv_rows?: number[]; candidate_scopus_eids?: string[]; ambiguity_reason?: string | null}};
  source_conflicts?: SourceConflict[];
  conference_suggestions?: Record<string, string | null | undefined>;
  import_readiness?: ImportReadiness;
  date_enrichment?: Enrichment;
};
type SourceConflict = {field: string; reason_code?: string; bibtex_value?: string | null; scopus_value?: string | null; assessment: string; severity: string};
type ScopusAnalysis = {records: CsvRecord[]; unmatched_records: (CsvRecord & {match_status: string; candidate_entry_numbers?: number[]})[]; summary: Record<string, number>};
type ReadinessScope = {total: number; statuses: Record<string, number>; blockers: Record<string, number>};
type Analysis = {
  analysis_only: true; file_name: string; file_size_bytes: number; scopus_file_name?: string; total_entries: number; entries: AnalysisEntry[]; scopus?: ScopusAnalysis;
  summary: {total_entries: number; successfully_parsed: number; parse_errors: number; unsupported_types: number; exact_matches_already_in_database: number; new_candidates: number; needs_metadata_review: number; review_dimensions?: {duplicate_statuses: Record<string, number>; metadata_statuses: Record<string, number>; date_statuses: Record<string, number>; document_modules: Record<string, number>; missing_exact_publication_dates: number; missing_venues: number; valid_dois: number; missing_dois: number; no_duplicate_detected: number; potentially_new_needs_review: number; metadata_comparisons?: Record<string, number>; supplementary_metadata?: number; document_type_differences?: number; import_readiness?: Record<string, number>; readiness_blockers?: Record<string, number>; potentially_new?: number; readiness_summary?: {all_records: ReadinessScope; potentially_new: ReadinessScope}}};
};

const PRIMARY_FILTERS = [["ALL", "All primary results"], ["POTENTIALLY_NEW_NEEDS_REVIEW", "Potentially new — needs review"], ["NEW_CANDIDATE", "New candidates"], ["ALREADY_IN_DATABASE", "Already in database"], ["DUPLICATE_WITHIN_FILE", "Duplicate within BibTeX"], ["POSSIBLE_DUPLICATE", "Possible duplicate"], ["NEEDS_METADATA_REVIEW", "Needs metadata review"], ["PARSE_ERROR", "Parse errors"], ["UNSUPPORTED_TYPE", "Unsupported types"]] as const;
const PAGE_SIZE = 25;
const display = (value: string | null | undefined) => value || "—";
const friendly = (value: string | null | undefined) => display(value?.toLowerCase().replaceAll("_", " ").replace(/\b\w/g, character => character.toUpperCase()));
const authorNames = (authors: Author[] | undefined) => authors?.map(author => author.author_name_from_source).filter(Boolean).join("; ") || "—";

function dateOutcome(entry: AnalysisEntry) {
  const result = entry.date_enrichment;
  const suggested = result?.verification?.suggested_date;
  if (!entry.publication?.doi) return "DOI_UNAVAILABLE";
  if (!result) return entry.publication_date_status === "MISSING" ? "NOT_YET_VERIFIED" : "EXACT_BIBTEX";
  if (result.status === "IDENTITY_CONFLICT" || result.verification?.identity_status === "IDENTITY_CONFLICT") return "IDENTITY_CONFLICT";
  if (result.verification?.suggestion_status === "CONFLICTING_DATES") return "CONFLICTING_DATES";
  if (result.status === "UNAVAILABLE" || !result.verification) return "PROVIDER_FAILURE";
  if (!suggested) return "NO_RELIABLE_DATE";
  if (suggested.precision === "YEAR") return "YEAR_ONLY";
  if (suggested.precision === "MONTH") return "PARTIAL_DATE";
  return result.preferred?.is_exact_online || suggested.date_type.includes("ONLINE") ? "EXACT_ONLINE" : "EXACT_ALTERNATIVE";
}

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
  const [readinessFilter, setReadinessFilter] = useState("ALL");
  const [verificationScope, setVerificationScope] = useState("MISSING_EXACT");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("SOURCE");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<AnalysisEntry>();
  const [verifyingEntries, setVerifyingEntries] = useState<number[]>([]);
  const [verificationErrors, setVerificationErrors] = useState<Record<number, string>>({});
  const [reviewWorkspaceOpen, setReviewWorkspaceOpen] = useState(false);

  function resetTable() {
    setPrimaryFilter("ALL"); setDuplicateFilter("ALL"); setMetadataFilter("ALL"); setSourceFilter("ALL"); setDocumentFilter("ALL"); setConflictFilter("ALL"); setDateFilter("ALL"); setEnrichmentFilter("ALL"); setReadinessFilter("ALL");
    setQuery(""); setSort("SOURCE"); setPage(1); setSelected(undefined); setVerifyingEntries([]); setVerificationErrors({});
  }
  function selectBibFile(event: ChangeEvent<HTMLInputElement>) {
    requestRef.current?.abort(); enrichmentRef.current?.abort(); setBibFile(event.target.files?.[0]); setAnalysis(undefined); setReviewWorkspaceOpen(false); setError(""); resetTable();
  }
  function selectScopusFile(event: ChangeEvent<HTMLInputElement>) {
    requestRef.current?.abort(); enrichmentRef.current?.abort(); setScopusFile(event.target.files?.[0]); setAnalysis(undefined); setReviewWorkspaceOpen(false); setError(""); resetTable();
  }
  function clear() {
    requestRef.current?.abort(); enrichmentRef.current?.abort(); setBibFile(undefined); setScopusFile(undefined); setAnalysis(undefined); setReviewWorkspaceOpen(false); setError(""); resetTable();
    if (bibInputRef.current) bibInputRef.current.value = "";
    if (csvInputRef.current) csvInputRef.current.value = "";
  }
  async function analyze() {
    if (!bibFile || busy) return;
    const controller = new AbortController(); requestRef.current = controller;
    setBusy(true); setError(""); setAnalysis(undefined); setReviewWorkspaceOpen(false); resetTable();
    const form = new FormData(); form.append("file", bibFile);
    if (scopusFile) form.append("scopus_file", scopusFile);
    try {
      const result = await api<Analysis>("/publications/analyze-bibtex-file", {method: "POST", body: form, signal: controller.signal});
      if (requestRef.current === controller && !controller.signal.aborted) setAnalysis(result);
    } catch (cause) {
      if (requestRef.current === controller && (cause as Error).name !== "AbortError") setError((cause as ApiError).message || "The files could not be analyzed.");
    } finally {
      if (requestRef.current === controller) requestRef.current = null;
      if (requestRef.current === null) setBusy(false);
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
      (conflictFilter === "ALL" || entry.scopus_match?.metadata_comparison === conflictFilter) &&
      (dateFilter === "ALL" ||
        (dateFilter === "MISSING" && dateOutcome(entry) === "NOT_YET_VERIFIED") ||
        (dateFilter === "VERIFIED_EXACT" && ["EXACT_ONLINE", "EXACT_ALTERNATIVE", "EXACT_BIBTEX"].includes(dateOutcome(entry))) ||
        (dateFilter === "PARTIAL" && ["PARTIAL_DATE", "YEAR_ONLY"].includes(dateOutcome(entry))) ||
        (dateFilter === "PROVIDER_FAILURE" && ["PROVIDER_FAILURE", "NO_RELIABLE_DATE"].includes(dateOutcome(entry))) ||
        (dateFilter === "IDENTITY_CONFLICT" && dateOutcome(entry) === "IDENTITY_CONFLICT") ||
        (dateFilter === "DOI_UNAVAILABLE" && dateOutcome(entry) === "DOI_UNAVAILABLE")) &&
      (enrichmentFilter === "ALL" || entry.date_enrichment?.status === enrichmentFilter) &&
      (readinessFilter === "ALL" || entry.import_readiness?.status === readinessFilter || entry.import_readiness?.blockers.includes(readinessFilter)) &&
      (!search || [entry.citation_key, entry.publication?.title, entry.publication?.doi, entry.publication_year, authorNames(entry.publication?.authors), entry.document_classification?.scopus_document_type].join(" ").toLocaleLowerCase().includes(search))
    );
    return values.sort((left, right) => sort === "TITLE" ? (left.publication?.title || "").localeCompare(right.publication?.title || "") : sort === "YEAR" ? (right.publication_year || "").localeCompare(left.publication_year || "") : sort === "DISPOSITION" ? left.primary_disposition.localeCompare(right.primary_disposition) : left.entry_number - right.entry_number);
  }, [analysis, primaryFilter, duplicateFilter, metadataFilter, sourceFilter, documentFilter, conflictFilter, dateFilter, enrichmentFilter, readinessFilter, query, sort]);
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const eligibleForDateLookup = useMemo(() => {
    const seen = new Set<string>();
    return (verificationScope === "CURRENT_FILTERED" ? filtered : analysis?.entries || []).filter(entry => {
      const doi = entry.publication?.doi?.toLowerCase();
      if (!doi || entry.date_enrichment || entry.publication_date_status !== "MISSING" || entry.duplicate_status === "EXISTING_DATABASE" || entry.scopus_match?.status === "AMBIGUOUS" || seen.has(doi)) return false;
      seen.add(doi); return true;
    }).slice(0, 25);
  }, [analysis, filtered, verificationScope]);
  const readinessSummary = useMemo(() => {
    const summarize = (entries: AnalysisEntry[]): ReadinessScope => {
      const statuses: Record<string, number> = {}, blockers: Record<string, number> = {};
      entries.forEach(entry => {
        const readiness = entry.import_readiness;
        if (!readiness) return;
        statuses[readiness.status] = (statuses[readiness.status] || 0) + 1;
        readiness.blockers.forEach(blocker => { blockers[blocker] = (blockers[blocker] || 0) + 1; });
      });
      return {total: entries.length, statuses, blockers};
    };
    const entries = analysis?.entries || [];
    const computed = {
      allRecords: summarize(entries),
      potentiallyNew: summarize(entries.filter(entry => entry.duplicate_status === "NO_DUPLICATE_DETECTED")),
    };
    // The server summary is the canonical initial contract. Entry-derived
    // totals take over whenever readiness is present so session-only DOI
    // verification can update the visible counters without a database write.
    const serialized = analysis?.summary.review_dimensions?.readiness_summary;
    return entries.some(entry => Boolean(entry.import_readiness)) || !serialized ? computed : {
      allRecords: serialized.all_records,
      potentiallyNew: serialized.potentially_new,
    };
  }, [analysis]);
  const dateOutcomeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    analysis?.entries.forEach(entry => {
      const outcome = dateOutcome(entry);
      counts[outcome] = (counts[outcome] || 0) + 1;
    });
    return counts;
  }, [analysis]);

  async function enrichDates(entries?: AnalysisEntry[] | MouseEvent<HTMLButtonElement>) {
    const selectedEntries = Array.isArray(entries) ? entries : eligibleForDateLookup;
    if (!selectedEntries.length || enriching) return;
    const controller = new AbortController(); enrichmentRef.current = controller;
    const entryNumbers = selectedEntries.map(entry => entry.entry_number);
    setEnriching(true); setError(""); setVerifyingEntries(entryNumbers);
    setVerificationErrors(current => {
      const next = {...current}; entryNumbers.forEach(entryNumber => delete next[entryNumber]); return next;
    });
    try {
      const result = await api<{results: Enrichment[]}>("/publications/analyze-bibtex-file/enrich-dates", {
        method: "POST", signal: controller.signal, body: JSON.stringify({entries: selectedEntries.map(entry => ({entry_number: entry.entry_number, doi: entry.publication?.doi, title: entry.publication?.title, publication_year: entry.publication_year, bibtex_date: entry.publication?.publication_date}))}),
      });
      if (!Array.isArray(result.results)) throw new Error("The server returned an invalid date-verification result. Please retry.");
      const byNumber = new Map(result.results.map(item => [item.entry_number, item]));
      const byDoi = new Map(result.results.filter(item => item.status !== "DUPLICATE_REQUEST").map(item => [item.doi.toLowerCase(), item]));
      const applyEnrichment = (entry: AnalysisEntry) => {
        const date_enrichment = byNumber.get(entry.entry_number) || (entry.publication?.doi ? byDoi.get(entry.publication.doi.toLowerCase()) : undefined);
        if (!date_enrichment) return entry;
        const exactVerified = date_enrichment.verification?.suggested_date?.precision === "DAY";
        const missing_metadata = exactVerified ? entry.missing_metadata.filter(field => field !== "exact publication date") : entry.missing_metadata;
        const unresolvedAuthors = entry.publication?.authors?.some(author => author.matching_status === "SUGGESTED");
        const nextMetadataStatus = entry.metadata_status === "NEEDS_REVIEW" && !missing_metadata.length && !unresolvedAuthors ? "COMPLETE" : entry.metadata_status;
        const import_readiness = exactVerified && entry.import_readiness ? (() => {
          const blockers = entry.import_readiness.blockers.filter(blocker =>
            blocker !== "DATE_VERIFICATION_REQUIRED" &&
            !(blocker === "MISSING_REQUIRED_METADATA" && nextMetadataStatus === "COMPLETE")
          );
          return {...entry.import_readiness, blockers, status: blockers[0] || "READY_FOR_REVIEW"};
        })() : entry.import_readiness;
        return {...entry, date_enrichment, missing_metadata,
          metadata_status: nextMetadataStatus,
          publication_date_status: exactVerified ? "DOI_SUGGESTION_AVAILABLE" : entry.publication_date_status, import_readiness};
      };
      setAnalysis(current => current ? {...current, entries: current.entries.map(applyEnrichment)} : current);
      // The dialog retains a selected-entry snapshot. Refresh it as well so a
      // verification completed while the dialog is open is visible immediately.
      setSelected(current => current ? applyEnrichment(current) : current);
      const missing = entryNumbers.filter(entryNumber => !byNumber.has(entryNumber));
      if (missing.length) setVerificationErrors(current => ({...current, ...Object.fromEntries(missing.map(entryNumber => [entryNumber, "The server did not return a result for this DOI. Please retry."]))}));
    } catch (cause) {
      if ((cause as Error).name !== "AbortError") {
        const message = (cause as ApiError).message || "Date enrichment could not be completed. Please retry.";
        setError(message);
        setVerificationErrors(current => ({...current, ...Object.fromEntries(entryNumbers.map(entryNumber => [entryNumber, message]))}));
      }
    } finally {if (enrichmentRef.current === controller) enrichmentRef.current = null; setVerifyingEntries([]); setEnriching(false);}
  }

  function cancelEnrichment() {enrichmentRef.current?.abort();}
  const selectedIsVerifying = Boolean(selected && verifyingEntries.includes(selected.entry_number));
  const selectedVerificationError = selected ? verificationErrors[selected.entry_number] : undefined;

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
      <div className="row-between" style={{marginTop: 16}}><div><h2>Analysis review</h2><p className="muted">Open a separate, browser-local preparation workspace to review proposed Journal and Conference records. It never calls a publication save endpoint.</p></div><button type="button" onClick={() => setReviewWorkspaceOpen(open => !open)}>{reviewWorkspaceOpen ? "Close Bulk Review Workspace" : "Open Bulk Review Workspace"}</button></div>
      {reviewWorkspaceOpen && bibFile && <BulkPublicationReviewWorkspace analysis={analysis} bibtexFile={bibFile} scopusFile={scopusFile} onVerify={async entries => { await enrichDates(entries as AnalysisEntry[]); }}/>}
      <div className="analysis-summary" aria-label="BibTeX and Scopus analysis summary">
        <section><h3>Source reconciliation</h3><div className="analysis-summary-cards">{[["BibTeX entries", analysis.total_entries], ["CSV records", analysis.scopus?.summary.total_csv_records], ["Unique source matches", analysis.scopus?.summary.unique_csv_matches], ["Ambiguous CSV", analysis.scopus?.summary.ambiguous_csv_records], ["BibTeX-only", analysis.scopus?.summary.bibtex_only_entries], ["CSV-only", analysis.scopus?.summary.csv_only_records], ["Identity conflicts", analysis.scopus?.summary.identity_conflicts]].filter(([, value]) => value !== undefined).map(([label, value]) => <div className="analysis-card" key={String(label)}><span>{label}</span><strong>{value}</strong></div>)}</div></section>
        <section><h3>Metadata comparison</h3><div className="analysis-summary-cards">{[["Consistent", analysis.summary.review_dimensions?.metadata_comparisons?.CONSISTENT], ["Informational differences", analysis.summary.review_dimensions?.metadata_comparisons?.INFORMATIONAL_DIFFERENCES], ["Requires review", analysis.summary.review_dimensions?.metadata_comparisons?.REQUIRES_REVIEW], ["Supplementary metadata", analysis.summary.review_dimensions?.supplementary_metadata], ["Document-type differences", analysis.summary.review_dimensions?.document_type_differences]].map(([label, value]) => <div className="analysis-card" key={String(label)}><span>{label}</span><strong>{value ?? 0}</strong></div>)}</div></section>
        <section><h3>Import readiness</h3><p className="muted">Potentially new means no existing or upload duplicate was detected. The following overlapping review blockers are counted only within those {readinessSummary.potentiallyNew.total} records; they do not authorize import.</p><div className="analysis-summary-cards">{[["Potentially new — no duplicate detected", readinessSummary.potentiallyNew.total], ["Ready for human review", readinessSummary.potentiallyNew.statuses.READY_FOR_REVIEW], ["Missing exact dates", readinessSummary.potentiallyNew.blockers.DATE_VERIFICATION_REQUIRED], ["Classification review", readinessSummary.potentiallyNew.blockers.CLASSIFICATION_REVIEW_REQUIRED], ["Contributor review", readinessSummary.potentiallyNew.blockers.CONTRIBUTOR_REVIEW_REQUIRED], ["Claimant required", readinessSummary.potentiallyNew.blockers.CLAIMANT_REQUIRED], ["Special / unsupported", (readinessSummary.potentiallyNew.blockers.SPECIAL_RECORD_POLICY_REVIEW || 0) + (readinessSummary.potentiallyNew.blockers.UNSUPPORTED_MODULE || 0)]].map(([label, value]) => <div className="analysis-card" key={String(label)}><span>{label}</span><strong>{value ?? 0}</strong></div>)}</div></section>
        <section><h3>Duplicate detection</h3><div className="analysis-summary-cards">{[["Existing database", analysis.summary.review_dimensions?.duplicate_statuses.EXISTING_DATABASE], ["Duplicate upload", analysis.summary.review_dimensions?.duplicate_statuses.DUPLICATE_WITHIN_UPLOAD], ["Possible duplicate", analysis.summary.review_dimensions?.duplicate_statuses.POSSIBLE_DUPLICATE], ["No duplicate detected", analysis.summary.review_dimensions?.no_duplicate_detected]].map(([label, value]) => <div className="analysis-card" key={String(label)}><span>{label}</span><strong>{value ?? 0}</strong></div>)}</div></section>
        <section><h3>Metadata quality</h3><div className="analysis-summary-cards">{[["Missing exact dates", analysis.summary.review_dimensions?.missing_exact_publication_dates], ["Missing venues", analysis.summary.review_dimensions?.missing_venues], ["Valid DOI", analysis.summary.review_dimensions?.valid_dois], ["Missing DOI", analysis.summary.review_dimensions?.missing_dois], ["Metadata complete", analysis.summary.review_dimensions?.metadata_statuses.COMPLETE], ["Potentially new — needs review", analysis.summary.review_dimensions?.potentially_new_needs_review]].map(([label, value]) => <div className="analysis-card" key={String(label)}><span>{label}</span><strong>{value ?? 0}</strong></div>)}</div></section>
        {analysis.scopus && <section><h3>Document classification</h3><div className="analysis-summary-cards">{[["Journal candidates", analysis.summary.review_dimensions?.document_modules.JOURNAL], ["Conference candidates", analysis.summary.review_dimensions?.document_modules.CONFERENCE], ["Books / Chapters", analysis.summary.review_dimensions?.document_modules.BOOKS_CHAPTERS], ["Special records", analysis.summary.review_dimensions?.document_modules.SPECIAL], ["Document-type conflicts", analysis.scopus.summary.classification_conflicts]].map(([label, value]) => <div className="analysis-card" key={String(label)}><span>{label}</span><strong>{value ?? 0}</strong></div>)}</div></section>}
        <section><h3>DOI enrichment</h3><div className="analysis-summary-cards">{[["Remaining eligible DOI records", eligibleForDateLookup.length], ["Exact online dates", dateOutcomeCounts.EXACT_ONLINE], ["Exact alternative dates", dateOutcomeCounts.EXACT_ALTERNATIVE], ["Partial dates", dateOutcomeCounts.PARTIAL_DATE], ["Year only", dateOutcomeCounts.YEAR_ONLY], ["Conflicting dates", dateOutcomeCounts.CONFLICTING_DATES], ["Identity conflicts", dateOutcomeCounts.IDENTITY_CONFLICT], ["Provider failures", dateOutcomeCounts.PROVIDER_FAILURE], ["No reliable date", dateOutcomeCounts.NO_RELIABLE_DATE], ["Not yet verified", dateOutcomeCounts.NOT_YET_VERIFIED], ["DOI unavailable", dateOutcomeCounts.DOI_UNAVAILABLE]].map(([label, value]) => <div className="analysis-card" key={String(label)}><span>{label}</span><strong>{value || 0}</strong></div>)}</div></section>
      </div>
      {eligibleForDateLookup.length > 0 && <div className="notice" style={{marginTop: 16}}><strong>Automatic publication-date verification</strong><p>Up to {eligibleForDateLookup.length} unique eligible DOI rows will be checked sequentially against Crossref and, where needed, DataCite, OpenAlex, and structured publisher metadata. Results require review and never update records.</p><div className="actions"><label className="field" style={{minWidth: 240}}>Verification scope<select value={verificationScope} onChange={event => setVerificationScope(event.target.value)} disabled={enriching}><option value="MISSING_EXACT">Eligible records missing exact dates</option><option value="CURRENT_FILTERED">Current filtered subset</option></select></label><button type="button" className="secondary" onClick={enrichDates} disabled={enriching}>{enriching ? "Verifying publication dates…" : "Verify Publication Dates Automatically"}</button>{enriching && <button type="button" className="secondary" onClick={cancelEnrichment}>Cancel request</button>}</div></div>}
      <div className="grid" style={{marginTop: 20}}>
        <label className="field">Find entries<input value={query} onChange={event => {setQuery(event.target.value); setPage(1);}} placeholder="Title, DOI, citation key, author or Scopus type"/></label>
        <label className="field">Primary review<select value={primaryFilter} onChange={event => {setPrimaryFilter(event.target.value); setPage(1);}}>{PRIMARY_FILTERS.map(([value, name]) => <option value={value} key={value}>{name}</option>)}</select></label>
        <label className="field">Duplicate status<select value={duplicateFilter} onChange={event => {setDuplicateFilter(event.target.value); setPage(1);}}><option value="ALL">All duplicate statuses</option>{["EXISTING_DATABASE", "DUPLICATE_WITHIN_UPLOAD", "POSSIBLE_DUPLICATE", "NO_DUPLICATE_DETECTED", "UNDETERMINED"].map(value => <option key={value} value={value}>{friendly(value)}</option>)}</select></label>
        <label className="field">Metadata readiness<select value={metadataFilter} onChange={event => {setMetadataFilter(event.target.value); setPage(1);}}><option value="ALL">All metadata states</option>{["COMPLETE", "NEEDS_REVIEW", "UNSUPPORTED", "PARSE_ERROR"].map(value => <option key={value} value={value}>{friendly(value)}</option>)}</select></label>
        {analysis.scopus && <label className="field">Source identity<select value={sourceFilter} onChange={event => {setSourceFilter(event.target.value); setPage(1);}}><option value="ALL">All source identities</option>{["MATCHED", "AMBIGUOUS", "BIBTEX_ONLY", "IDENTITY_CONFLICT"].map(value => <option key={value} value={value}>{friendly(value)}</option>)}</select></label>}
        <label className="field">Document type<select value={documentFilter} onChange={event => {setDocumentFilter(event.target.value); setPage(1);}}><option value="ALL">All suggested modules</option>{["JOURNAL", "CONFERENCE", "BOOKS_CHAPTERS", "SPECIAL", "POLICY_REVIEW"].map(value => <option key={value} value={value}>{friendly(value)}</option>)}</select></label>
        {analysis.scopus && <label className="field">Metadata comparison<select value={conflictFilter} onChange={event => {setConflictFilter(event.target.value); setPage(1);}}><option value="ALL">All metadata comparisons</option>{["CONSISTENT", "INFORMATIONAL_DIFFERENCES", "REQUIRES_REVIEW", "IDENTITY_CONFLICT"].map(value => <option key={value} value={value}>{friendly(value)}</option>)}</select></label>}
        <label className="field">Publication date<select value={dateFilter} onChange={event => {setDateFilter(event.target.value); setPage(1);}}><option value="ALL">All date states</option><option value="MISSING">Missing date — not yet verified</option><option value="VERIFIED_EXACT">Verified exact date</option><option value="PARTIAL">Partial or year-only date</option><option value="IDENTITY_CONFLICT">Identity conflict</option><option value="PROVIDER_FAILURE">Provider failure / no reliable date</option><option value="DOI_UNAVAILABLE">DOI unavailable</option></select></label>
        <label className="field">DOI enrichment<select value={enrichmentFilter} onChange={event => {setEnrichmentFilter(event.target.value); setPage(1);}}><option value="ALL">All enrichment states</option><option value="FOUND">Date suggestion found</option><option value="IDENTITY_CONFLICT">Identity conflict</option><option value="UNAVAILABLE">Provider unavailable</option></select></label>
        <label className="field">Import readiness<select value={readinessFilter} onChange={event => {setReadinessFilter(event.target.value); setPage(1);}}><option value="ALL">All readiness states</option>{["READY_FOR_REVIEW", "DATE_VERIFICATION_REQUIRED", "MISSING_REQUIRED_METADATA", "CLASSIFICATION_REVIEW_REQUIRED", "CONTRIBUTOR_REVIEW_REQUIRED", "CLAIMANT_REQUIRED", "DUPLICATE_EXISTING", "DUPLICATE_UPLOAD", "POSSIBLE_DUPLICATE", "SOURCE_IDENTITY_AMBIGUOUS", "SPECIAL_RECORD_POLICY_REVIEW", "UNSUPPORTED_MODULE"].map(value => <option key={value} value={value}>{friendly(value)}</option>)}</select></label>
        <label className="field">Sort entries<select value={sort} onChange={event => {setSort(event.target.value); setPage(1);}}><option value="SOURCE">Original source order</option><option value="TITLE">Title</option><option value="YEAR">Publication year</option><option value="DISPOSITION">Primary review result</option></select></label>
      </div>
      <div className="table-wrap" style={{marginTop: 16}}><table className="analysis-review-table"><thead><tr>{["#", "Publication title", "Year", "Document type", "Suggested module", "DOI", "Duplicate", "Metadata", "Date", "Source identity", "Metadata differences", "Import readiness", "Review"].map(heading => <th key={heading}>{heading}</th>)}</tr></thead><tbody>{visible.map(entry => <tr key={entry.entry_number}><td>{entry.entry_number}</td><td className="analysis-title" title={entry.publication?.title || ""}>{display(entry.publication?.title)}<small>{display(entry.citation_key)}</small></td><td>{display(entry.publication_year)}</td><td>{display(entry.document_classification?.bibtex_type)}{entry.document_classification?.scopus_document_type ? <small>{entry.document_classification.scopus_document_type}</small> : ""}</td><td>{friendly(entry.document_classification?.suggested_module)}</td><td className="analysis-doi" title={entry.publication?.doi || ""}>{display(entry.publication?.doi)}</td><td><span className="badge">{friendly(entry.duplicate_status)}</span></td><td><span className="badge">{friendly(entry.metadata_status)}</span></td><td><span className="badge">{friendly(entry.publication_date_status)}</span></td><td><span className="badge">{friendly(entry.scopus_match?.status || "BIBTEX_ONLY")}</span></td><td><span className="badge">{friendly(entry.scopus_match?.metadata_comparison || "NOT_COMPARED")}</span>{entry.source_conflicts?.length ? <small>{entry.source_conflicts.length} difference{entry.source_conflicts.length === 1 ? "" : "s"}</small> : ""}</td><td><span className="badge">{friendly(entry.import_readiness?.status || "NOT_ASSESSED")}</span></td><td><button type="button" className="secondary small" onClick={() => setSelected(entry)}>Review</button></td></tr>)}</tbody></table>{!visible.length && <p className="empty">No entries match this analysis filter.</p>}</div>
      <div className="row-between" style={{marginTop: 16}}><span className="muted">Showing {filtered.length ? (page - 1) * PAGE_SIZE + 1 : 0}–{Math.min(page * PAGE_SIZE, filtered.length)} of {filtered.length} matching entries</span><div className="actions"><button type="button" className="secondary small" disabled={page === 1} onClick={() => setPage(value => value - 1)}>Previous</button><span>Page {page} of {totalPages}</span><button type="button" className="secondary small" disabled={page === totalPages} onClick={() => setPage(value => value + 1)}>Next</button></div></div>
      {analysis.scopus && analysis.scopus.unmatched_records.length > 0 && <section className="panel" style={{marginTop: 20}}><h3>Scopus-only or ambiguous source records</h3><p className="muted">These are CSV source rows requiring manual review. They are not added to any publication queue.</p><div className="table-wrap"><table><thead><tr><th>CSV row</th><th>EID</th><th>Title</th><th>Year</th><th>DOI</th><th>Result</th></tr></thead><tbody>{analysis.scopus.unmatched_records.map(record => <tr key={record.source_row}><td>{record.source_row}</td><td>{display(record.eid)}</td><td>{display(record.title)}</td><td>{display(record.year)}</td><td>{display(record.doi)}</td><td>{friendly(record.match_status)}</td></tr>)}</tbody></table></div></section>}
      {selected && <section className="panel" role="dialog" aria-label={`BibTeX entry ${selected.entry_number} details`} style={{marginTop: 20}}><div className="row-between"><h2>Entry {selected.entry_number} · {display(selected.citation_key)}</h2><button type="button" className="secondary" onClick={() => setSelected(undefined)}>Close details</button></div><p><span className="badge">{friendly(selected.primary_disposition)}</span></p><h3>Independent review dimensions</h3><p>Duplicate: <strong>{friendly(selected.duplicate_status)}</strong> · Metadata: <strong>{friendly(selected.metadata_status)}</strong> · Eligibility: <strong>{friendly(selected.import_eligibility)}</strong></p><p>Document: BibTeX <strong>{display(selected.document_classification?.bibtex_type)}</strong>{selected.document_classification?.scopus_document_type ? <> · Scopus <strong>{selected.document_classification.scopus_document_type}</strong></> : ""} · Suggested module: <strong>{friendly(selected.document_classification?.suggested_module)}</strong></p>{selected.document_classification?.classification_conflict && <p className="error">The BibTeX and Scopus document classifications conflict; resolve manually.</p>}
        <h3>Publication identity</h3><dl className="detail-grid"><div><dt>Title</dt><dd>{display(selected.publication?.title)}</dd></div><div><dt>DOI</dt><dd>{display(selected.publication?.doi)}</dd></div><div><dt>Year</dt><dd>{display(selected.publication_year)}</dd></div><div><dt>Citation key</dt><dd>{display(selected.citation_key)}</dd></div><div><dt>Scopus EID</dt><dd>{display(selected.scopus_match?.csv_record?.eid)}</dd></div><div><dt>Source match</dt><dd>{friendly(selected.scopus_match?.status || "BIBTEX_ONLY")}</dd></div></dl>
        <h3>Duplicate analysis</h3><ul>{duplicateMatches(selected).map((match, index) => <li key={`${match.publication_id || match.entry_number}-${index}`}>{match.publication_id ? <>Database publication <Link href={`/publications/${match.publication_id}`}>#{match.publication_id}{match.is_active === false ? " (inactive)" : ""}</Link> · {display(match.title || match.doi)}{match.claiming_faculty ? <> · Current claimant: {match.claiming_faculty.name} (Faculty #{match.claiming_faculty.faculty_id})</> : ""}</> : <>BibTeX entry {match.entry_number} · {display(match.citation_key)} · {display(match.reason)}</>}</li>)}{!duplicateMatches(selected).length && <li>No duplicate match detected.</li>}</ul>
        {selected.repeated_citation_keys.length > 0 && <p className="muted">The citation key is also used by BibTeX entry {selected.repeated_citation_keys.map(match => match.entry_number).join(", ")}. Citation keys are review metadata, not publication identifiers.</p>}
        <h3>Source matching</h3>{selected.scopus_match?.csv_record ? <p>Source identity: <strong>{friendly(selected.scopus_match.status)}</strong> · Matched Scopus CSV row {selected.scopus_match.csv_record.source_row} ({display(selected.scopus_match.csv_record.eid)}) by {selected.scopus_match.matching_evidence?.method || "review"}. CSV title: {display(selected.scopus_match.csv_record.title)}.</p> : <p>{selected.scopus_match?.matching_evidence?.ambiguity_reason ? `No unique source match: ${friendly(selected.scopus_match.matching_evidence.ambiguity_reason)}. Candidate CSV rows: ${selected.scopus_match.matching_evidence.candidate_csv_rows?.join(", ") || "—"}.` : "No CSV candidate was identified for this BibTeX entry."}</p>}
        <h3>Metadata comparison</h3><p><strong>{friendly(selected.scopus_match?.metadata_comparison || "NOT_COMPARED")}</strong> · Differences describe source metadata and do not by themselves change publication identity.</p>
        {selected.source_conflicts && selected.source_conflicts.length > 0 && <div className="table-wrap"><table><thead><tr><th>Field</th><th>Reason</th><th>BibTeX</th><th>Scopus CSV</th><th>Assessment</th></tr></thead><tbody>{selected.source_conflicts.map((conflict, index) => <tr key={`${conflict.field}-${index}`}><td>{conflict.field}</td><td>{friendly(conflict.reason_code)}</td><td>{display(conflict.bibtex_value)}</td><td>{display(conflict.scopus_value)}</td><td><span className="badge">{friendly(conflict.severity)}</span>{conflict.assessment}</td></tr>)}</tbody></table></div>}
        {selected.document_classification?.suggested_module === "CONFERENCE" && <><h3>Conference / proceedings metadata</h3><dl className="detail-grid"><div><dt>Conference name</dt><dd>{display(selected.conference_suggestions?.conference_name)}</dd></div><div><dt>Proceedings title</dt><dd>{display(selected.conference_suggestions?.proceedings_title)}</dd></div><div><dt>Conference event date</dt><dd>{display(selected.conference_suggestions?.conference_date)}</dd></div><div><dt>Conference location</dt><dd>{display(selected.conference_suggestions?.conference_location)}</dd></div><div><dt>Publisher</dt><dd>{display(selected.conference_suggestions?.publisher)}</dd></div><div><dt>ISBN / ISSN</dt><dd>{display(selected.conference_suggestions?.isbn || selected.conference_suggestions?.issn)}</dd></div></dl><p className="muted">Conference event information is separate from the publication date.</p></>}
        {selected.import_readiness && <><h3>Import readiness checklist</h3><div className="table-wrap"><table><thead><tr><th>Requirement</th><th>Result</th></tr></thead><tbody><tr><td>Publication identity</td><td>{friendly(selected.scopus_match?.status || "BIBTEX_ONLY")}</td></tr><tr><td>Existing duplicate</td><td>{friendly(selected.duplicate_status)}</td></tr><tr><td>Document classification</td><td>{selected.document_classification?.classification_conflict ? "Review required" : "Supported / review as shown"}</td></tr><tr><td>Required metadata</td><td>{selected.missing_metadata.length ? `Missing: ${selected.missing_metadata.join(", ")}` : "Complete"}</td></tr><tr><td>Publication date</td><td>{friendly(dateOutcome(selected))}</td></tr><tr><td>Internal contributors</td><td>{selected.import_readiness.contributors.matched_faculty} Faculty · {selected.import_readiness.contributors.matched_students} Students · {selected.import_readiness.contributors.unresolved_internal} unresolved internal · {selected.import_readiness.contributors.external_or_unmatched} external or unmatched</td></tr><tr><td>Claiming Faculty</td><td>{selected.import_readiness.claimant_candidates.length ? `Selection required from ${selected.import_readiness.claimant_candidates.length} eligible Faculty candidate(s)` : "Required — no eligible candidate identified"}</td></tr><tr><td>Final import authorization</td><td>Not available in Stage 1D</td></tr></tbody></table></div>{selected.import_readiness.claimant_candidates.length > 0 && <><h4>Eligible claiming Faculty candidates</h4><div className="table-wrap"><table><thead><tr><th>Faculty</th><th>Faculty ID</th><th>Current Department</th><th>Match evidence</th></tr></thead><tbody>{selected.import_readiness.claimant_candidates.map(candidate => <tr key={candidate.faculty_id}><td>{candidate.name}</td><td>{candidate.faculty_id}</td><td>{candidate.department ? `${candidate.department.name} (${candidate.department.code})` : "No current Department recorded"}</td><td>{friendly(candidate.matching_status)}{candidate.confidence != null ? ` · ${Math.round(candidate.confidence * 100)}%` : ""}</td></tr>)}</tbody></table></div><p className="muted">Department information is the current Faculty Master affiliation only; no historical attribution is inferred during analysis.</p></>}{selected.import_readiness.blockers.length > 0 && <ul>{selected.import_readiness.blockers.map(blocker => <li key={blocker}><strong>{friendly(blocker)}</strong> · {selected.import_readiness?.explanations[blocker]}</li>)}</ul>}</>}
        <h3>Publication date review</h3>
        {selectedIsVerifying ? <p role="status">Verifying this DOI automatically. This may take a moment while date providers are checked.</p> : selected.date_enrichment?.verification ? <>
          <p>Identity: <strong>{friendly(selected.date_enrichment.verification.identity_status)}</strong> · Result: <strong>{friendly(selected.date_enrichment.verification.suggestion_status)}</strong>{selected.date_enrichment.verification.requires_review ? " · Manual verification required." : ""}</p>
          {selected.date_enrichment.verification.suggested_date ? <p>Suggested date: <strong>{selected.date_enrichment.verification.suggested_date.date}</strong> ({selected.date_enrichment.verification.suggested_date.precision}, {friendly(selected.date_enrichment.verification.suggested_date.date_type)}) from {selected.date_enrichment.verification.suggested_date.source}. This remains analysis-only.</p> : <p>{selected.date_enrichment.error || "No reliable date was found after checking the available providers."}</p>}
          {selected.date_enrichment.verification.bibtex_date_conflict && <p className="error">The suggested date differs from the original BibTeX date. Both values are preserved for manual verification.</p>}
          {selected.date_enrichment.verification.candidates.length > 0 && <div className="table-wrap"><table><thead><tr><th>Source</th><th>Date</th><th>Precision</th><th>Type</th><th>Evidence</th></tr></thead><tbody>{selected.date_enrichment.verification.candidates.map(candidate => <tr key={`${candidate.source}-${candidate.source_field}-${candidate.date}`}><td>{candidate.source}</td><td>{candidate.date}</td><td>{candidate.precision}</td><td>{friendly(candidate.date_type)}</td><td><a href={candidate.source_url} target="_blank" rel="noreferrer">{candidate.source_field}</a> · {friendly(candidate.assessment)}</td></tr>)}</tbody></table></div>}
          {selected.date_enrichment.verification.provider_failures.length > 0 && <p className="muted">Unavailable evidence: {selected.date_enrichment.verification.provider_failures.map(item => `${item.source}: ${item.error}`).join("; ")}</p>}
          {selected.publication?.doi && !selected.date_enrichment.verification.suggested_date && <button type="button" className="secondary small" onClick={() => enrichDates([selected])} disabled={enriching}>Retry DOI verification</button>}
        </> : selected.date_enrichment || selectedVerificationError ? <>
          <p className="error" role="alert">{selectedVerificationError || selected.date_enrichment?.error || "Verification did not return reliable date evidence. Please retry."}</p>
          {selected.publication?.doi && <button type="button" className="secondary small" onClick={() => enrichDates([selected])} disabled={enriching}>Retry DOI verification</button>}
        </> : <>
          <p>{selected.publication?.publication_date ? `BibTeX exact date: ${selected.publication.publication_date}` : "No exact BibTeX date. Automatic verification may be available."}</p>
          {selected.publication?.doi && <button type="button" className="secondary small" onClick={() => enrichDates([selected])} disabled={enriching}>Verify this DOI automatically</button>}
        </>}
        <h3>Metadata and authors</h3><p>{selected.missing_metadata.length ? `Missing: ${selected.missing_metadata.join(", ")}` : "No required metadata gaps detected by analysis."}</p><p>{authorNames(selected.publication?.authors)}</p><h3>Original BibTeX</h3><pre className="raw-bibtex">{selected.raw_bibtex || "No recoverable raw BibTeX is available for this parse error."}</pre>
      </section>}
    </>}
  </section>;
}
