"use client";

import { createContext, useContext, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, label, Person } from "@/lib/api";
import { useDateRange } from "@/components/DateRange";

type RecordSummary = { id: number; title: string; claimed: boolean; publication_date: string | null; publication_type?: string; work_type?: string; indexing?: string[]; quartile?: string | null; classification?: string; application_number?: string | null; filing_date?: string | null; grant_date?: string | null; patent_type?: string | null };
type FdpSummary = { id: number; title: string; activity_type: string; organizing_institution?: string | null; publication_date: string | null; start_date?: string | null; end_date?: string | null; duration_value?: number | string | null; duration_unit?: string | null; role?: string | null; roles: string[]; is_active: boolean };
type CertificationSummary = { id: number; title: string; publication_date: string | null; completion_date?: string | null; issue_date?: string | null; expiry_date?: string | null; credential_id?: string | null; category: string; provider: string; status: string; is_active: boolean };
type FundingRole = { role: string; agency_role_label?: string | null };
type FundingSummary = { id: number; title: string; publication_date: string | null; reporting_date?: string | null; category: string; funding_agency?: string | null; status: string; start_date?: string | null; end_date?: string | null; proposed_amount?: number | string | null; sanctioned_amount?: number | string | null; contract_amount?: number | string | null; amount_received?: number | string | null; amount_utilized?: number | string | null; currency?: string; roles: string[]; investigator_roles: FundingRole[] };
type FundingTotals = { projects: number; submitted_under_review: number; awarded: number; proposed_amount: number | string | null; sanctioned_amount: number | string | null; contract_amount: number | string | null; amount_received: number | string | null; amount_utilized: number | string | null };
type Profile = { faculty: Person; from_date: string; to_date: string; summary: Record<string, number | null>; publications: RecordSummary[]; patents: RecordSummary[]; books: RecordSummary[]; fdp: FdpSummary[]; certifications: CertificationSummary[]; funding_projects: FundingSummary[]; funding_summary: { sponsored_research: FundingTotals; consultancy: FundingTotals; internal_grants: FundingTotals }; unavailable_modules: Record<string, string> };

const Context = createContext<((id: number) => void) | null>(null);
const summaryLabels = {
  journal: "Journal Publications", conference: "Conference Publications", patents: "Patents", books: "Books / Chapters",
  fdp: "Faculty Development Activities", certifications_completed: "Completed Certifications", certifications_in_progress: "In-Progress Certifications",
  sponsored_research: "Sponsored Research Projects", consultancy: "Consultancy Projects", internal_grants: "Internal Grants",
};

function fundingRoleLabel(role: string) {
  if (role === "LEAD_PI") return "Lead PI / Principal Investigator";
  if (role === "MEMBER_PI") return "Member PI";
  if (role === "CO_PI") return "Co-PI / Co-Investigator";
  if (role === "ADMIN_PI") return "Admin PI";
  if (role === "PI") return "Historical Principal Investigator";
  if (role === "CO_INVESTIGATOR") return "Historical Co-Investigator";
  return label(role);
}

function amount(value: number | string | null | undefined) {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(Number(value));
}

function dateRange(start?: string | null, end?: string | null) {
  if (start && end) return `${start} to ${end}`;
  return start || end || "—";
}

export function FacultyName({ id, name }: { id: number; name: string }) {
  const open = useContext(Context);
  return <button type="button" className="dash-faculty-name" data-faculty-id={id} onClick={() => open?.(id)} aria-label={`Open Faculty Research Details: ${name}`}>{name}</button>;
}

export function FacultyDetailsProvider({ children }: { children: React.ReactNode }) {
  const { range } = useDateRange();
  const [identity, setIdentity] = useState<number | null>(null);
  const [profile, setProfile] = useState<Profile>();
  const [error, setError] = useState("");
  const [tab, setTab] = useState("summary");
  const [retry, setRetry] = useState(0);
  const dialog = useRef<HTMLDialogElement>(null);
  const dates = new URLSearchParams(range).toString();

  useEffect(() => {
    if (identity === null) return;
    let active = true;
    setProfile(undefined); setError("");
    api<Profile>(`/research/faculty/${identity}?${dates}`)
      .then((data) => { if (active) setProfile(data); })
      .catch((requestError: Error) => { if (active) setError(requestError.message); });
    return () => { active = false; };
  }, [identity, dates, retry]);

  useEffect(() => {
    if (identity !== null && !dialog.current?.open) dialog.current?.showModal();
    else if (identity === null) dialog.current?.close();
  }, [identity]);

  function open(id: number) { setTab("summary"); setIdentity(id); }

  function recordTable(module: "publications" | "patents" | "books") {
    const rows = profile?.[module] || [];
    const headings = module === "publications"
      ? ["Title", "Type", "Publication Date", "Claim status", "Indexing", "Quartile", "Classification"]
      : module === "patents"
        ? ["Title", "Type", "Application Number", "Filed", "Published", "Granted", "Claim status"]
        : ["Title", "Type", "Publication Date", "Claim status"];
    return <><p className="muted">{module === "patents" ? "Includes patents with any filing, publication, or grant event in the selected period. Each parent patent counts once." : "Unique active records in the selected inclusive date range."}</p><div className="table-wrap"><table><thead><tr>{headings.map((heading) => <th key={heading}>{heading}</th>)}</tr></thead><tbody>{rows.map((row) => <tr key={row.id}><td className="title"><Link href={`/${module}/${row.id}?${dates}`} onClick={() => setIdentity(null)}>{row.title}</Link></td>{module === "patents" ? <><td>{row.patent_type ? label(row.patent_type) : "Not configured"}</td><td>{row.application_number || "—"}</td><td>{row.filing_date || "—"}</td><td>{row.publication_date || "—"}</td><td>{row.grant_date || "—"}</td><td>{row.claimed ? "Claimed" : "Inventor"}</td></> : <><td>{label(row.publication_type || row.work_type || "UNKNOWN")}</td><td>{row.publication_date}</td><td>{row.claimed ? "Claimed" : module === "books" ? "Contributor" : "Co-author"}</td>{module === "publications" && <><td>{row.indexing?.map(label).join(", ") || "Unknown"}</td><td>{row.quartile || "Unknown"}</td><td>{label(row.classification || "UNKNOWN")}</td></>}</>}</tr>)}</tbody></table></div>{!rows.length && <p className="dash-empty">No {module === "books" ? "books / chapters" : module} in the selected period.</p>}</>;
  }

  function fdpTable() {
    const rows = profile?.fdp || [];
    return <><p className="muted">Active activities are included by inclusive start date. One activity remains one row even if this Faculty member has several participation roles.</p><div className="table-wrap"><table><thead><tr><th>Activity</th><th>Type</th><th>Organizer</th><th>Dates / duration</th><th>Participation roles</th><th>Status</th><th>Details</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id}><td>{row.title}</td><td>{label(row.activity_type)}</td><td>{row.organizing_institution || "—"}</td><td>{row.end_date ? dateRange(row.start_date, row.end_date) : `${row.start_date || "—"}${row.duration_value ? ` · ${row.duration_value} ${label(row.duration_unit || "")}` : ""}`}</td><td>{row.roles.map(label).join(", ") || "—"}</td><td>{row.is_active ? "Active" : "Inactive"}</td><td><Link href={`/fdp/${row.id}?${dates}`} onClick={() => setIdentity(null)}>View details</Link></td></tr>)}</tbody></table></div>{!rows.length && <p className="dash-empty">No Faculty Development Activities in the selected period.</p>}</>;
  }

  function certificationTable() {
    const rows = profile?.certifications || [];
    return <><p className="muted">Completed certifications use the selected inclusive completion-date range. Active in-progress certifications are current work and appear independently of that range.</p><div className="table-wrap"><table><thead><tr><th>Certification / course</th><th>Category</th><th>Provider</th><th>Status</th><th>Issue / completion</th><th>Expiry</th><th>Credential</th><th>Details</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id}><td>{row.title}</td><td>{label(row.category)}</td><td>{row.provider || "—"}</td><td>{label(row.status)}</td><td>{row.status === "IN_PROGRESS" ? `${row.issue_date || "—"} / Current work` : `${row.issue_date || "—"} / ${row.completion_date || "—"}`}</td><td>{row.expiry_date || "—"}</td><td>{row.credential_id || "—"}</td><td><Link href={`/certifications/${row.id}?${dates}`} onClick={() => setIdentity(null)}>View details</Link></td></tr>)}</tbody></table></div>{!rows.length && <p className="dash-empty">No completed certifications in the selected period or active in-progress certifications.</p>}</>;
  }

  function fundingTotals() {
    const summary = profile?.funding_summary;
    const rows = [
      { label: "Sponsored Research", value: summary?.sponsored_research, details: (totals: FundingTotals) => <>Submitted / under review: {totals.submitted_under_review}; awarded: {totals.awarded}. Proposed: {amount(totals.proposed_amount)}; sanctioned: {amount(totals.sanctioned_amount)}.</> },
      { label: "Consultancy", value: summary?.consultancy, details: (totals: FundingTotals) => <>Contract / approved: {amount(totals.contract_amount)}; received: {amount(totals.amount_received)}.</> },
      { label: "Internal Grants", value: summary?.internal_grants, details: (totals: FundingTotals) => <>Sanctioned: {amount(totals.sanctioned_amount)}; utilized: {amount(totals.amount_utilized)}.</> },
    ];
    return <section className="panel"><h3>Funding summary for projects involving this Faculty member</h3><p className="muted">Amounts are project totals, not personal funding allocations. Awarded financial totals exclude submitted and under-review proposals; a dash means no amount is recorded.</p><div className="table-wrap"><table><thead><tr><th>Category</th><th>Associated projects</th><th>Summary</th></tr></thead><tbody>{rows.map((row) => <tr key={row.label}><td>{row.label}</td><td>{row.value?.projects ?? "—"}</td><td>{row.value ? row.details(row.value) : "—"}</td></tr>)}</tbody></table></div></section>;
  }

  function fundingTable() {
    const rows = profile?.funding_projects || [];
    return <>{fundingTotals()}<p className="muted">Records use the established reporting date: sanction date, otherwise proposal submission date, otherwise start date. Only Faculty Master-linked investigator associations appear here.</p><div className="table-wrap"><table><thead><tr><th>Project</th><th>Category</th><th>Agency / client</th><th>Faculty roles</th><th>Reporting date</th><th>Project period</th><th>Relevant financial fields</th><th>Status</th><th>Details</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id}><td>{row.title}</td><td>{label(row.category)}</td><td>{row.funding_agency || "—"}</td><td>{row.investigator_roles.map((role) => role.agency_role_label || fundingRoleLabel(role.role)).join(", ") || "—"}</td><td>{row.reporting_date || row.publication_date || "—"}</td><td>{dateRange(row.start_date, row.end_date)}</td><td>{row.category === "SPONSORED_RESEARCH" ? <>Proposed: {amount(row.proposed_amount)}<br />Sanctioned: {amount(row.sanctioned_amount)}</> : row.category === "CONSULTANCY" ? <>Contract: {amount(row.contract_amount)}<br />Received: {amount(row.amount_received)}</> : <>Sanctioned: {amount(row.sanctioned_amount)}<br />Utilized: {amount(row.amount_utilized)}</>}</td><td>{label(row.status)}</td><td><Link href={`/funding-projects/${row.id}?${dates}`} onClick={() => setIdentity(null)}>View details</Link></td></tr>)}</tbody></table></div>{!rows.length && <p className="dash-empty">No Faculty Master-linked funding records in the selected period.</p>}</>;
  }

  const tabs = { summary: "Summary", publications: "Publications", patents: "Patents", books: "Books / Chapters", fdp: "FDP Activities", certifications: "Certifications", funding_projects: "Funding Projects" };
  return <Context.Provider value={open}>{children}<dialog className="research-dashboard faculty-dialog" ref={dialog} aria-labelledby="faculty-details-title" onCancel={() => setIdentity(null)} onClose={() => setIdentity(null)}><div className="dash-modal-header"><div><h2 id="faculty-details-title">Faculty Research Details</h2>{profile && <><h3>{profile.faculty.name}</h3><p>{profile.faculty.employee_id} · {profile.faculty.designation || "Designation not provided"}</p></>}<p>{range.from_date} to {range.to_date} · Inclusive dates</p></div><button className="secondary small" onClick={() => setIdentity(null)} aria-label="Close Faculty Research Details">Close</button></div>{error ? <div className="error" role="alert">{error}<button onClick={() => setRetry((value) => value + 1)}>Retry</button></div> : !profile ? <div className="dash-loading" role="status">Loading faculty research details…</div> : <><div className="dash-tabs" role="tablist" aria-label="Faculty research sections">{Object.entries(tabs).map(([key, text]) => <button type="button" role="tab" aria-selected={tab === key} aria-controls="faculty-tab-panel" key={key} onClick={() => setTab(key)}>{text}</button>)}</div><div id="faculty-tab-panel" role="tabpanel" aria-label={tab === "summary" ? "Summary" : label(tab)}>{tab === "summary" ? <><div className="dash-profile-summary">{Object.entries(summaryLabels).map(([key, text]) => <div key={key}><span>{text}</span><strong>{profile.summary[key] === null ? "Not configured" : profile.summary[key] ?? "—"}</strong></div>)}</div><p>Claim and authored/inventor counts remain available in the module record tables. No composite score is calculated.</p></> : tab === "fdp" ? fdpTable() : tab === "certifications" ? certificationTable() : tab === "funding_projects" ? fundingTable() : recordTable(tab as "publications" | "patents" | "books")}</div></>}</dialog></Context.Provider>;
}
