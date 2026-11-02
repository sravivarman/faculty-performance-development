"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import DeleteConfirmationDialog from "@/components/DeleteConfirmationDialog";
import { api, label, Masters } from "@/lib/api";

type FieldInfo = { id: string; label: string; group: string; availability: "AVAILABLE" | "CALCULATED" | "UNAVAILABLE"; note?: string | null };
type ReportRow = { publication_id: number; faculty_id: number | null; values: Record<string, string | number> };
type Preview = { headers: { id: string; heading: string }[]; items: ReportRow[]; total: number; unique_publication_count: number; row_mode: string; page: number; page_size: number | "all" };
type CitationResult = { items: { publication_id: number; formatted_citation: string; completeness_status: string; missing_fields: string[] }[]; total_selected: number; complete: number; incomplete: number; needs_review: number; excluded_needs_review: number };
type Config = {
  faculty_ids: number[]; publication_type: "ALL" | "JOURNAL" | "CONFERENCE"; period_mode: "ALL" | "ACADEMIC_YEAR" | "CUSTOM";
  academic_year_id?: number; from_date?: string; to_date?: string; title_keyword?: string; venue_keyword?: string;
  publication_year?: string; indexing?: string; quartile?: string; row_mode: "PUBLICATION" | "FACULTY";
  sort: "DATE_DESC" | "DATE_ASC" | "YEAR" | "FACULTY" | "TITLE" | "VENUE"; fields: string[]; headings: Record<string, string>;
};
type SavedConfig = Partial<Config> & { mode?: "TABLE" | "CITATIONS"; citation_style?: "IEEE" | "APA" | "HARVARD" };
type Template = { id: number; name: string; description?: string | null; config: SavedConfig; is_builtin: boolean };

const defaults: Config = { faculty_ids: [], publication_type: "ALL", period_mode: "ALL", row_mode: "PUBLICATION", sort: "DATE_DESC", fields: ["serial_number", "publication_title", "vardhaman_faculty_authors", "all_authors", "journal_name", "publication_date", "doi"], headings: {} };
const builtInNames: Record<string, string> = { GENERAL_REGISTER: "General Publication Register", RESEARCH_QUALITY: "Research Quality Report", DEPARTMENT_CONSOLIDATED: "Department Consolidated Publications" };

function cleanRequest(config: Config, page = 1, pageSize: number | "all" = 25) {
  return Object.fromEntries(Object.entries({ ...config, publication_year: config.publication_year ? Number(config.publication_year) : undefined, page, page_size: pageSize }).filter(([, value]) => value !== undefined && value !== ""));
}

export default function PublicationReportBuilder() {
  const [mode, setMode] = useState<"TABLE" | "CITATIONS">("TABLE");
  const [config, setConfig] = useState<Config>(defaults);
  const [fields, setFields] = useState<FieldInfo[]>([]);
  const [builtIns, setBuiltIns] = useState<{ id: string; name: string; fields: string[] }[]>([]);
  const [masters, setMasters] = useState<Masters>();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [preview, setPreview] = useState<Preview>();
  const [citations, setCitations] = useState<CitationResult>();
  const [citationStyle, setCitationStyle] = useState<"IEEE" | "APA" | "HARVARD">("IEEE");
  const [includeNeedsReview, setIncludeNeedsReview] = useState(false);
  const [facultySearch, setFacultySearch] = useState("");
  const [fieldSearch, setFieldSearch] = useState("");
  const [templateName, setTemplateName] = useState("");
  const [templateDescription, setTemplateDescription] = useState("");
  const [selectedTemplate, setSelectedTemplate] = useState<number | null>(null);
  const [confirmTemplateDeletion, setConfirmTemplateDeletion] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function refreshTemplates() {
    try { setTemplates(await api<Template[]>("/publication-reports/templates")); } catch (reason) { setError((reason as Error).message); }
  }

  useEffect(() => {
    api<Masters>("/masters").then(setMasters).catch((reason) => setError((reason as Error).message));
    api<{ fields: FieldInfo[]; built_in_templates: { id: string; name: string; fields: string[] }[] }>("/publication-reports/fields")
      .then((data) => { setFields(data.fields); setBuiltIns(data.built_in_templates); })
      .catch((reason) => setError((reason as Error).message));
    refreshTemplates();
  }, []);

  const groupedFields = useMemo(() => fields.filter((item) => !fieldSearch || item.label.toLowerCase().includes(fieldSearch.toLowerCase()) || item.group.toLowerCase().includes(fieldSearch.toLowerCase())).reduce<Record<string, FieldInfo[]>>((groups, item) => ({ ...groups, [item.group]: [...(groups[item.group] || []), item] }), {}), [fields, fieldSearch]);
  const matchingFaculty = useMemo(() => masters?.faculty.filter((person) => `${person.name} ${person.employee_id || ""}`.toLowerCase().includes(facultySearch.toLowerCase())) || [], [masters, facultySearch]);
  const selectedFields = config.fields.map((id) => fields.find((item) => item.id === id)).filter(Boolean) as FieldInfo[];

  function update(values: Partial<Config>) { setConfig((current) => ({ ...current, ...values })); setPreview(undefined); setCitations(undefined); }
  function clearFilters() {
    update({ faculty_ids: [], publication_type: "ALL", period_mode: "ALL", academic_year_id: undefined, from_date: undefined, to_date: undefined,
      title_keyword: undefined, venue_keyword: undefined, publication_year: undefined, indexing: undefined, quartile: undefined });
    setFacultySearch("");
  }
  function toggleFaculty(id: number) { update({ faculty_ids: config.faculty_ids.includes(id) ? config.faculty_ids.filter((value) => value !== id) : [...config.faculty_ids, id] }); }
  function toggleField(item: FieldInfo) { if (item.availability === "UNAVAILABLE") return; update({ fields: config.fields.includes(item.id) ? config.fields.filter((id) => id !== item.id) : [...config.fields, item.id] }); }
  function moveField(id: string, direction: -1 | 1) { const index = config.fields.indexOf(id); const next = index + direction; if (next < 0 || next >= config.fields.length) return; const fields = [...config.fields]; [fields[index], fields[next]] = [fields[next], fields[index]]; update({ fields }); }
  function applyTemplate(fields: string[]) { update({ ...defaults, fields }); setSelectedTemplate(null); }

  async function generate(page = 1) {
    if (!config.fields.length) { setError("Select at least one available report field."); return; }
    setLoading(true); setError("");
    try {
      if (mode === "TABLE") setPreview(await api<Preview>("/publication-reports/preview", { method: "POST", body: JSON.stringify(cleanRequest(config, page)) }));
      else setCitations(await api<CitationResult>("/publication-reports/citations", { method: "POST", body: JSON.stringify({ ...cleanRequest(config), citation_style: citationStyle, include_needs_review: includeNeedsReview }) }));
    } catch (reason) { setError((reason as Error).message); } finally { setLoading(false); }
  }

  async function saveTemplate(updateExisting = false) {
    if (!templateName.trim()) { setError("Enter a template name."); return; }
    const payload = { name: templateName.trim(), description: templateDescription || null, config: { fields: config.fields, headings: config.headings, row_mode: config.row_mode, sort: config.sort, mode, citation_style: citationStyle } };
    try {
      const result = await api<Template>(updateExisting && selectedTemplate ? `/publication-reports/templates/${selectedTemplate}` : "/publication-reports/templates", { method: updateExisting && selectedTemplate ? "PUT" : "POST", body: JSON.stringify(payload) });
      setSelectedTemplate(result.id); await refreshTemplates();
    } catch (reason) { setError((reason as Error).message); }
  }

  async function deleteTemplate() {
    if (!selectedTemplate) return;
    setLoading(true); setError("");
    try { await api(`/publication-reports/templates/${selectedTemplate}`, { method: "DELETE" }); setSelectedTemplate(null); setTemplateName(""); setTemplateDescription(""); setConfirmTemplateDeletion(false); await refreshTemplates(); } catch (reason) { setError((reason as Error).message); } finally { setLoading(false); }
  }

  async function download(path: string, extension: string, citation = false) {
    setError("");
    try {
      const payload = citation ? { ...cleanRequest(config, 1, "all"), citation_style: citationStyle, include_needs_review: includeNeedsReview } : cleanRequest(config, 1, "all");
      const response = await fetch(`/api${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      if (!response.ok) throw new Error((await response.json().catch(() => ({ detail: "Export failed" }))).detail || "Export failed");
      const link = document.createElement("a"); link.href = URL.createObjectURL(await response.blob()); link.download = `publications-report.${extension}`; link.click(); URL.revokeObjectURL(link.href);
    } catch (reason) { setError((reason as Error).message); }
  }

  async function copyCitations() { if (citations) await navigator.clipboard.writeText(citations.items.map((item, index) => citationStyle === "IEEE" ? `[${index + 1}] ${item.formatted_citation}` : item.formatted_citation).join("\n\n")); }

  return <>
    <div className="page-heading"><div><div className="eyebrow">Publications</div><h1>Report Builder</h1><p className="muted">Configure a reusable publication table or verified bibliography without changing source records.</p></div><Link href="/publications">← Publications overview</Link></div>
    <div className="actions"><button className={mode === "TABLE" ? "" : "secondary"} onClick={() => setMode("TABLE")}>Custom Table Report</button><button className={mode === "CITATIONS" ? "" : "secondary"} onClick={() => setMode("CITATIONS")}>Citation List</button></div>
    {error && <div className="error" role="alert">{error}</div>}
    <section className="panel"><div className="row-between"><h2>Report scope</h2><button type="button" className="secondary small" onClick={clearFilters}>Clear report filters</button></div><div className="filters">
      <label className="field" htmlFor="report-publication-type">Publication Type<select id="report-publication-type" value={config.publication_type} onChange={(event) => update({ publication_type: event.target.value as Config["publication_type"] })}><option value="ALL">All Publications</option><option value="JOURNAL">Journal Publications</option><option value="CONFERENCE">Conference Publications</option></select></label>
      <label className="field" htmlFor="report-period-mode">Reporting Period<select id="report-period-mode" value={config.period_mode} onChange={(event) => update({ period_mode: event.target.value as Config["period_mode"] })}><option value="ALL">All Dates</option><option value="ACADEMIC_YEAR">Academic Year</option><option value="CUSTOM">Custom Dates</option></select></label>
      {config.period_mode === "ACADEMIC_YEAR" && <label className="field" htmlFor="report-academic-year">Academic Year<select id="report-academic-year" value={config.academic_year_id || ""} onChange={(event) => update({ academic_year_id: Number(event.target.value) || undefined })}><option value="">Select Academic Year</option>{masters?.academic_years.map((year) => <option key={year.id} value={year.id}>{year.name} · {year.start_date} to {year.end_date}</option>)}</select></label>}
      {config.period_mode === "CUSTOM" && <><label className="field" htmlFor="report-from-date">From Date<input id="report-from-date" type="date" value={config.from_date || ""} onChange={(event) => update({ from_date: event.target.value })}/></label><label className="field" htmlFor="report-to-date">To Date<input id="report-to-date" type="date" value={config.to_date || ""} onChange={(event) => update({ to_date: event.target.value })}/></label></>}
      <label className="field" htmlFor="report-title-keyword">Title keyword<input id="report-title-keyword" value={config.title_keyword || ""} onChange={(event) => update({ title_keyword: event.target.value })}/></label>
      <label className="field" htmlFor="report-venue-keyword">Journal / Conference<input id="report-venue-keyword" value={config.venue_keyword || ""} onChange={(event) => update({ venue_keyword: event.target.value })}/></label>
      <label className="field" htmlFor="report-publication-year">Publication Year<input id="report-publication-year" type="number" min="1900" value={config.publication_year || ""} onChange={(event) => update({ publication_year: event.target.value })}/></label>
      <label className="field" htmlFor="report-indexing">Indexing<select id="report-indexing" value={config.indexing || ""} onChange={(event) => update({ indexing: event.target.value })}><option value="">All Indexing</option>{["SCOPUS", "SCI", "SCIE", "ESCI", "WEB_OF_SCIENCE", "UGC_CARE", "OTHER", "NONE", "UNKNOWN"].map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></label>
      <label className="field" htmlFor="report-quartile">Quartile<select id="report-quartile" value={config.quartile || ""} onChange={(event) => update({ quartile: event.target.value })}><option value="">All</option>{["Q1", "Q2", "Q3", "Q4", "NOT_APPLICABLE", "UNKNOWN"].map((value) => <option key={value}>{label(value)}</option>)}</select></label>
      <label className="field" htmlFor="report-sort">Sort<select id="report-sort" value={config.sort} onChange={(event) => update({ sort: event.target.value as Config["sort"] })}>{[["DATE_DESC", "Publication date — newest first"], ["DATE_ASC", "Publication date — oldest first"], ["YEAR", "Publication year"], ["FACULTY", "Faculty name"], ["TITLE", "Publication title"], ["VENUE", "Journal / conference"]].map(([value, text]) => <option key={value} value={value}>{text}</option>)}</select></label>
      <label className="field" htmlFor="report-row-mode">Row Mode<select id="report-row-mode" value={config.row_mode} onChange={(event) => update({ row_mode: event.target.value as Config["row_mode"] })}><option value="PUBLICATION">Publication-wise</option><option value="FACULTY">Faculty-wise</option></select></label>
    </div>
    <label className="field" htmlFor="report-faculty-search" style={{ marginTop: 16 }}>Find Faculty<input id="report-faculty-search" value={facultySearch} placeholder="Search name or employee ID" onChange={(event) => setFacultySearch(event.target.value)}/></label>
    <div className="report-faculty-list">{matchingFaculty.map((person) => <label className="check" key={person.id}><input type="checkbox" checked={config.faculty_ids.includes(person.id)} onChange={() => toggleFaculty(person.id)}/><span className="report-faculty-label">{person.name}{person.employee_id ? ` (${person.employee_id})` : ""}</span>{!person.is_active && <span className="badge">Historical</span>}</label>)}</div>
    </section>
    {mode === "TABLE" ? <>
      <section className="panel"><div className="row-between"><div><h2>Columns</h2><p className="muted">Unavailable fields are shown for transparency and cannot be selected.</p></div><div className="actions"><button className="secondary small" onClick={() => update({ fields: fields.filter((item) => item.availability !== "UNAVAILABLE").map((item) => item.id) })}>Select All Available</button><button className="secondary small" onClick={() => update({ fields: [] })}>Clear Selection</button></div></div>
        <div className="actions"><label className="field" htmlFor="report-field-search" style={{ flex: 1 }}>Find a field<input id="report-field-search" value={fieldSearch} onChange={(event) => setFieldSearch(event.target.value)}/></label><label className="field" htmlFor="report-built-in-template">Built-in Template<select id="report-built-in-template" defaultValue="" onChange={(event) => { const template = builtIns.find((item) => item.id === event.target.value); if (template) applyTemplate(template.fields); event.currentTarget.value = ""; }}><option value="">Choose a template</option>{builtIns.map((item) => <option key={item.id} value={item.id}>{builtInNames[item.id] || item.name}</option>)}</select></label></div>
        <div className="report-field-groups">{Object.entries(groupedFields).map(([group, items]) => <section key={group}><h3>{group}</h3>{items.map((item) => <label className={`check report-field${item.availability === "UNAVAILABLE" ? " unavailable" : ""}`} key={item.id} title={item.note || ""}><input type="checkbox" disabled={item.availability === "UNAVAILABLE"} checked={config.fields.includes(item.id)} onChange={() => toggleField(item)}/><span>{item.label}</span><small>{item.availability === "CALCULATED" ? "Calculated" : item.availability === "UNAVAILABLE" ? `Unavailable${item.note ? ` — ${item.note}` : ""}` : "Stored"}</small></label>)}</section>)}</div>
      </section>
      <section className="panel"><h2>Selected columns · {selectedFields.length}</h2>{selectedFields.map((item, index) => <div className="report-column-row" key={item.id}><strong>{index + 1}. {item.label}</strong><input aria-label={`${item.label} heading`} value={config.headings[item.id] || ""} placeholder="Default heading" onChange={(event) => update({ headings: { ...config.headings, [item.id]: event.target.value } })}/><button className="secondary small" disabled={!index} onClick={() => moveField(item.id, -1)}>Move up</button><button className="secondary small" disabled={index === selectedFields.length - 1} onClick={() => moveField(item.id, 1)}>Move down</button><button className="secondary small" onClick={() => update({ headings: Object.fromEntries(Object.entries(config.headings).filter(([id]) => id !== item.id)) })}>Restore</button></div>)}</section>
    </> : <section className="panel"><h2>Citation List</h2><div className="filters"><label className="field" htmlFor="report-citation-style">Citation Style<select id="report-citation-style" value={citationStyle} onChange={(event) => setCitationStyle(event.target.value as typeof citationStyle)}><option value="IEEE">IEEE</option><option value="APA">APA 7th Edition</option><option value="HARVARD">Harvard Author–Date</option></select></label><label className="check"><input type="checkbox" checked={includeNeedsReview} onChange={(event) => setIncludeNeedsReview(event.target.checked)}/> Include truthful entries requiring review</label></div><p className="muted">Citations use recorded author order. Items missing a title are excluded by default and reported for review.</p></section>}
    <section className="panel"><div className="row-between"><div><h2>Reusable layout</h2><p className="muted">Layouts are shared because this application has no template ownership system.</p></div><div className="actions"><button onClick={() => saveTemplate(false)}>Save as New</button>{selectedTemplate && <><button className="secondary" onClick={() => saveTemplate(true)}>Update</button><button className="danger" onClick={() => setConfirmTemplateDeletion(true)}>Delete</button></>}</div></div><div className="filters"><label className="field" htmlFor="report-template-name">Template Name<input id="report-template-name" value={templateName} onChange={(event) => setTemplateName(event.target.value)}/></label><label className="field" htmlFor="report-template-description">Description<input id="report-template-description" value={templateDescription} onChange={(event) => setTemplateDescription(event.target.value)}/></label><label className="field" htmlFor="report-template-load">Load Custom Template<select id="report-template-load" value={selectedTemplate || ""} onChange={(event) => { const template = templates.find((item) => item.id === Number(event.target.value)); setSelectedTemplate(template?.id || null); if (template) { update({ ...defaults, ...template.config, faculty_ids: config.faculty_ids, period_mode: config.period_mode, academic_year_id: config.academic_year_id, from_date: config.from_date, to_date: config.to_date }); setTemplateName(template.name); setTemplateDescription(template.description || ""); setMode((template.config.mode as typeof mode) || "TABLE"); } }}><option value="">Choose saved layout</option>{templates.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></div></section>
    <div className="savebar"><div><strong>{mode === "TABLE" ? "Custom Table Report" : `${citationStyle} Citation List`}</strong><div className="muted">Preview and export use the same filtered source records.</div></div><div className="actions"><button onClick={() => generate()} disabled={loading}>{loading ? "Generating…" : "Generate Preview"}</button>{mode === "TABLE" && <button className="secondary" onClick={() => download("/publication-reports/export/xlsx", "xlsx")}>Export Excel</button>}{mode === "CITATIONS" && citations && <><button className="secondary" onClick={copyCitations}>Copy to Clipboard</button><button className="secondary" onClick={() => download("/publication-reports/citations/export/docx", "docx", true)}>Export Word</button><button className="secondary" onClick={() => download("/publication-reports/citations/export/pdf", "pdf", true)}>Export PDF</button></>}</div></div>
    {mode === "TABLE" && preview && <section className="panel report-preview"><div className="row-between"><div><h2>Preview · {preview.total} report rows · {preview.unique_publication_count} unique publications</h2><p className="muted">{preview.row_mode === "FACULTY" ? "Faculty-wise rows can repeat one publication for different linked faculty." : "Publication-wise rows contain each unique publication once."}</p></div><div className="actions"><button className="secondary small" disabled={preview.page <= 1 || loading} onClick={() => generate(preview.page - 1)}>Previous</button><span className="muted">Page {preview.page}</span><button className="secondary small" disabled={preview.items.length === 0 || preview.page * Number(preview.page_size) >= preview.total || loading} onClick={() => generate(preview.page + 1)}>Next</button></div></div><div className="table-wrap"><table><thead><tr>{preview.headers.map((header) => <th key={header.id}>{header.heading}</th>)}</tr></thead><tbody>{preview.items.map((row) => <tr key={`${row.publication_id}-${row.faculty_id || "publication"}`}>{preview.headers.map((header) => <td key={header.id}>{String(row.values[header.id] ?? "")}</td>)}</tr>)}</tbody></table></div>{!preview.items.length && <div className="empty">No publications match the selected filters. Try clearing Quartile, Faculty, or Reporting Period.</div>}</section>}
    {mode === "CITATIONS" && citations && <section className="panel"><h2>Citation validation</h2><p className="muted">Selected: {citations.total_selected} · Complete: {citations.complete} · Incomplete: {citations.incomplete} · Needs review: {citations.needs_review} · Excluded by default: {citations.excluded_needs_review}</p>{citations.items.map((item, index) => <article className="citation-entry" key={item.publication_id}><strong>{citationStyle === "IEEE" ? `[${index + 1}] ` : ""}</strong>{item.formatted_citation}<small>{item.completeness_status}{item.missing_fields.length ? ` · Missing: ${item.missing_fields.join(", ")}` : ""}</small></article>)}</section>}
    <DeleteConfirmationDialog open={confirmTemplateDeletion} title="Delete report layout?" recordName={templateName || "Selected report layout"} description="This permanently removes the saved layout configuration. It does not remove publications or report data." busy={loading} onCancel={() => setConfirmTemplateDeletion(false)} onConfirm={deleteTemplate}/>
  </>;
}
