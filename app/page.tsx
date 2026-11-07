"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import DateRangeFilter, { useDateRange } from "@/components/DateRange";
import { api, Masters } from "@/lib/api";
import { currency, moduleLink, ResearchOverview } from "@/lib/research-overview";
import { DashboardError, DashboardFrame, DashboardSection, KpiGrid, ResearchPageHeader } from "@/components/dashboard/UI";
import { Distribution, ResearchActivityTrend } from "@/components/dashboard/Charts";
import PublicationAnalytics from "@/components/dashboard/PublicationAnalytics";
import { PATENT_TYPES } from "@/lib/patents";
import FacultyContributionTable from "@/components/dashboard/FacultyContributionTable";

const activities = {
  journal: "Journals", conference: "Conferences", patents: "Patents", books: "Books / Chapters",
  fdp: "Faculty Development Activities", certifications: "Completed Certifications",
  certifications_in_progress: "Certifications In Progress", research_projects: "Sponsored Research",
  consultancy: "Consultancy", internal_grants: "Seed Money / Internal Grants",
};

const columns = {
  journal: "Journals", conference: "Conferences", publications_claimed: "Publications Claimed",
  publications_authored: "Publications Authored", patents_invented: "Patents", books: "Books / Chapters",
  fdp: "Faculty Development Activities", certifications: "Completed Certifications",
  certifications_in_progress: "Certifications In Progress", research_projects: "Sponsored Research",
  consultancy: "Consultancy", internal_grants: "Internal Grants",
};

type FundingTotals = Record<string, number>;
type Overview = Omit<ResearchOverview, "faculty_summary"> & {
  patent_types: Record<string, number>;
  funding_summary: { sponsored_research: FundingTotals; consultancy: FundingTotals; internal_grants: FundingTotals };
  faculty_summary: ({ id: number; name: string } & Record<keyof typeof columns, number | null>)[];
};
type ScopedOverview = {
  scope: { type: "INSTITUTION" | "DEPARTMENT" | "FACULTY"; department_id: number | null; faculty_id: number | null; label: string; attribution_mode: "CURRENT" | "AT_ACTIVITY_DATE"; attribution_label: string };
  totals: Record<string, number>;
  faculty_contributors: number;
  department_comparison: { id: number; code: string; name: string; is_active: boolean; totals: Record<string, number>; unique_records: number; faculty_contributors: number }[];
  collaboration: { unique_records: number; pairs: { department_a: { id: number; code: string; name: string }; department_b: { id: number; code: string; name: string }; records: number; publications: number; patents: number; books: number; research_projects: number; consultancy: number; internal_grants: number }[] };
  data_quality: Record<string, number>;
};
const scopedLabels = { publications: "Publications", patents: "Patents", books: "Books / Chapters", fdp: "FDP / Training", certifications: "Certifications", research_projects: "Sponsored Research", consultancy: "Consultancy", internal_grants: "Internal Grants" };

function FundingSummary({ report, onSelect }: { report?: Overview; onSelect: (key: string) => void }) {
  const rows = [
    { key: "research_projects", label: "Sponsored Research", totals: report?.funding_summary.sponsored_research,
      detail: (totals: FundingTotals) => <>Submitted / under review: {totals.submitted_under_review}; awarded: {totals.sanctioned}. Proposed: {currency(totals.proposed_amount || 0)}; sanctioned: {currency(totals.sanctioned_amount || 0)}.</> },
    { key: "consultancy", label: "Consultancy", totals: report?.funding_summary.consultancy,
      detail: (totals: FundingTotals) => <>Approved / contract amount: {currency(totals.contract_value || 0)}; amount received: {currency(totals.amount_received || 0)}.</> },
    { key: "internal_grants", label: "Seed Money / Internal Grants", totals: report?.funding_summary.internal_grants,
      detail: (totals: FundingTotals) => <>Amount sanctioned: {currency(totals.sanctioned_amount || 0)}; amount utilized: {currency(totals.amount_utilized || 0)}.</> },
  ];
  return <DashboardSection title="Funding at a glance" note="Financial award totals include only sanctioned, ongoing, or completed records. Submitted and under-review proposal budgets remain proposed amounts, not sanctioned awards.">
    <div className="table-wrap"><table><thead><tr><th>Funding category</th><th>Records</th><th>Reporting summary</th></tr></thead><tbody>
      {rows.map((row) => <tr key={row.key}><td>{row.label}</td><td><button className="link-button" onClick={() => onSelect(row.key)}>{row.totals?.total ?? "—"} records</button></td><td>{row.totals ? row.detail(row.totals) : "Loading funding summary…"}</td></tr>)}
    </tbody></table></div>
  </DashboardSection>;
}

export default function ResearchDashboard() {
  const { range, ready, setRange } = useDateRange();
  const router = useRouter();
  const [report, setReport] = useState<Overview>();
  const [masters, setMasters] = useState<Masters>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const [scope, setScope] = useState<"INSTITUTION" | "DEPARTMENT" | "FACULTY">("INSTITUTION");
  const [scopeDepartmentId, setScopeDepartmentId] = useState("");
  const [scopeFacultyId, setScopeFacultyId] = useState("");
  const [attributionMode, setAttributionMode] = useState<"CURRENT" | "AT_ACTIVITY_DATE">("CURRENT");
  const [scopedReport, setScopedReport] = useState<ScopedOverview>();
  const [scopedError, setScopedError] = useState("");
  const [scopedLoading, setScopedLoading] = useState(false);
  const query = new URLSearchParams(range).toString();
  const selectedAcademicYear = useMemo(() => masters?.academic_years.find((year) => year.start_date === range.from_date && year.end_date === range.to_date), [masters, range.from_date, range.to_date]);

  useEffect(() => { api<Masters>("/masters").then(setMasters).catch((reason: Error) => setError(reason.message)); }, []);
  useEffect(() => {
    if (!ready) return;
    let active = true;
    setLoading(true); setError("");
    api<Overview>(`/research/overview?${query}`)
      .then((data) => { if (active) setReport(data); })
      .catch((reason: Error) => { if (active) { setReport(undefined); setError(reason.message); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [query, ready, retry]);
  useEffect(() => {
    if (!ready || (scope === "DEPARTMENT" && !scopeDepartmentId) || (scope === "FACULTY" && !scopeFacultyId)) { setScopedReport(undefined); return; }
    let active = true;
    setScopedLoading(true); setScopedError("");
    const params = new URLSearchParams({ ...range, scope, attribution_mode: attributionMode });
    if (scope === "DEPARTMENT") params.set("department_id", scopeDepartmentId);
    if (scope === "FACULTY") params.set("faculty_id", scopeFacultyId);
    api<ScopedOverview>(`/research/scoped-overview?${params}`)
      .then((data) => { if (active) setScopedReport(data); })
      .catch((reason: Error) => { if (active) { setScopedReport(undefined); setScopedError(reason.message); } })
      .finally(() => { if (active) setScopedLoading(false); });
    return () => { active = false; };
  }, [range, ready, scope, scopeDepartmentId, scopeFacultyId, attributionMode]);

  function navigate(key: string, extra: Record<string, string> = {}) {
    const params = new URLSearchParams({ ...range, ...extra });
    const fundingRoutes: Record<string, string> = { research_projects: "/research-projects", consultancy: "/consultancy", internal_grants: "/seed-money" };
    if (fundingRoutes[key]) { router.push(`${fundingRoutes[key]}?${params}`); return; }
    if (key === "fdp") { router.push(`/fdp?${params}`); return; }
    if (key === "certifications" || key === "certifications_in_progress") {
      if (key === "certifications_in_progress") { params.set("status", "IN_PROGRESS"); params.set("current_in_progress", "true"); }
      router.push(`/certifications?${params}`); return;
    }
    const module = key === "journal" || key === "conference" || key.startsWith("publications_") ? "publications" : key.startsWith("patents") ? "patents" : key;
    const metric = key === "journal" || key === "conference" ? key : key === "patents" || key === "patents_invented" ? "unique" : key.endsWith("claimed") ? "claimed" : key === "books" && extra.drill_faculty_id ? "participated" : "total";
    router.push(moduleLink(module, metric, range, extra));
  }

  return <DashboardFrame>
    <ResearchPageHeader title="Research Overview" subtitle="Institutional research performance and activity" />
    <section className="reporting-toolbar" aria-label="Institutional reporting controls"><DateRangeFilter /><div className="reporting-toolbar-controls">
      <label className="field">Academic Year<select aria-label="Academic Year Master" value={selectedAcademicYear?.id ?? ""} onChange={(event) => {
        const year = masters?.academic_years.find((item) => item.id === Number(event.target.value));
        if (year) setRange({ from_date: year.start_date, to_date: year.end_date }, "Custom");
      }}><option value="">Use selected reporting period</option>{masters?.academic_years.map((year) => <option key={year.id} value={year.id}>{year.name} · {year.start_date} to {year.end_date}</option>)}</select></label>
      <label className="field">Scope<select value={scope} onChange={(event) => { setScope(event.target.value as typeof scope); setScopeDepartmentId(""); setScopeFacultyId(""); }}><option value="INSTITUTION">Institution</option><option value="DEPARTMENT">Department</option><option value="FACULTY">Faculty</option></select></label>
      {scope === "DEPARTMENT" && <label className="field">Department<select value={scopeDepartmentId} onChange={(event) => setScopeDepartmentId(event.target.value)}><option value="">Select Department</option>{masters?.departments.map((department) => <option key={department.id} value={department.id}>{department.name} ({department.code}){department.is_active ? "" : " (historical)"}</option>)}</select></label>}
      {scope === "FACULTY" && <label className="field">Faculty<select value={scopeFacultyId} onChange={(event) => setScopeFacultyId(event.target.value)}><option value="">Select Faculty</option>{masters?.faculty.map((faculty) => <option key={faculty.id} value={faculty.id}>{faculty.name} ({faculty.employee_id}){faculty.department?.code ? ` — ${faculty.department.code}` : ""}</option>)}</select></label>}
      {scope !== "INSTITUTION" && <label className="field">Attribution<select value={attributionMode} onChange={(event) => setAttributionMode(event.target.value as typeof attributionMode)}><option value="CURRENT">Current Department Attribution</option><option value="AT_ACTIVITY_DATE">Activity-Date Attribution</option></select></label>}
    </div><p className="muted compact-note">Scope is analytical only. Department totals are contribution counts and are not additive across the Institution.</p></section>
    <DashboardSection title="Scoped institutional analysis">
      <DashboardError message={scopedError} />
      {scopedReport && <><p className="muted"><strong>{scopedReport.scope.label}</strong> · {scopedReport.scope.attribution_label} · {range.from_date} to {range.to_date}</p><KpiGrid labels={scopedLabels} counts={scopedReport.totals} loading={scopedLoading} /><p className="muted">Distinct Faculty contributors: {scopedReport.faculty_contributors}. A record is counted once within this scope even where several linked people contributed.</p></>}
      {!scopedReport && !scopedLoading && !scopedError && <p className="dash-empty">Choose the required Department or Faculty to view its scoped analysis.</p>}
    </DashboardSection>
    {scopedReport && scope !== "FACULTY" && <DashboardSection title="Department comparison" note="A shared record may be credited once to each verified contributing Department; these rows must not be summed into an institution total."><div className="table-wrap"><table><thead><tr><th>Department</th><th>Publications</th><th>Patents</th><th>Books / Chapters</th><th>FDP / Training</th><th>Certifications</th><th>Research Projects</th><th>Faculty Contributors</th></tr></thead><tbody>{scopedReport.department_comparison.map((department) => <tr key={department.id}><td>{department.name} ({department.code}){department.is_active ? "" : " · historical"}</td><td>{department.totals.publications}</td><td>{department.totals.patents}</td><td>{department.totals.books}</td><td>{department.totals.fdp}</td><td>{department.totals.certifications}</td><td>{department.totals.research_projects + department.totals.consultancy + department.totals.internal_grants}</td><td>{department.faculty_contributors}</td></tr>)}</tbody></table></div></DashboardSection>}
    {scopedReport && <DashboardSection title="Cross-department collaboration" note="A record qualifies when two or more verified Vardhaman Departments contributed. Pair counts can overlap when one record involves more than two Departments."><p className="muted">Unique cross-department records: {scopedReport.collaboration.unique_records}</p><div className="table-wrap"><table><thead><tr><th>Department A</th><th>Department B</th><th>Shared records</th><th>Publications</th><th>Patents</th><th>Books / Chapters</th><th>Projects</th></tr></thead><tbody>{scopedReport.collaboration.pairs.map((pair) => <tr key={`${pair.department_a.id}-${pair.department_b.id}`}><td>{pair.department_a.code}</td><td>{pair.department_b.code}</td><td>{pair.records}</td><td>{pair.publications}</td><td>{pair.patents}</td><td>{pair.books}</td><td>{pair.research_projects + pair.consultancy + pair.internal_grants}</td></tr>)}</tbody></table></div>{!scopedReport.collaboration.pairs.length && <p className="dash-empty">No verified cross-department collaboration is recorded for this scope and period.</p>}</DashboardSection>}
    {scopedReport && <DashboardSection title="Attribution data quality" note="Unverified historical affiliations are kept separate from confirmed Department totals."><div className="dash-profile-summary">{Object.entries(scopedReport.data_quality).map(([key, value]) => <div key={key}><span>{key.replaceAll("_", " ")}</span><strong>{value}</strong></div>)}</div></DashboardSection>}
    <DashboardError message={error} retry={() => setRetry((value) => value + 1)} />
    <h2>Research Activity</h2>
    <KpiGrid labels={activities} counts={{ ...report?.activity_totals, journal: report?.outcomes.journal, conference: report?.outcomes.conference }} loading={loading} onSelect={navigate} />
    <FundingSummary report={report} onSelect={navigate} />
    <ResearchActivityTrend />
    <Distribution title="Patents by Type" labels={PATENT_TYPES} counts={report?.patent_types || {}} loading={loading} error={error} onSelect={(patent_type) => navigate("patents", { patent_type })} />
    <PublicationAnalytics />
    <FacultyContributionTable columns={columns} rows={report?.faculty_summary || []} loading={loading} error={error} note="Unique authored Journal and Conference records. Claims and authorship remain separate. Patents count once for any lifecycle event in the selected range; books include eligible authors and editors. Certification current work is shown independently of the completion-date range." onSelect={(row, key) => navigate(key, ["fdp", "certifications", "certifications_in_progress", "research_projects", "consultancy", "internal_grants"].includes(key) ? { faculty_id: String(row.id) } : { drill_faculty_id: String(row.id) })} />
  </DashboardFrame>;
}
