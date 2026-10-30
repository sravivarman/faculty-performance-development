"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import DateRangeFilter, { useDateRange } from "@/components/DateRange";
import FacultyContributionTable from "@/components/dashboard/FacultyContributionTable";
import { DashboardFrame, KpiGrid, ResearchPageHeader } from "@/components/dashboard/UI";
import PaginationControls, { RecordPageSize } from "@/components/PaginationControls";
import { api, label, Masters, paginatedResult } from "@/lib/api";
import { FundingProject } from "@/components/FundingEditor";

type Category = "SPONSORED_RESEARCH" | "CONSULTANCY" | "INTERNAL_GRANT";
type PageResult = { items: FundingProject[]; total: number; page: number; page_size: number | "all" };
type FundingFacultyRow = {
  id: number;
  name: string;
  employee_id?: string | null;
  is_active: boolean;
  projects: number;
  department: string;
  roles: string[];
  role_lead_pi: number;
  role_member_pi: number;
  role_co_pi: number;
  role_admin_pi: number;
  role_beneficiary: number;
};
type Dashboard = { totals: Record<string, number>; role_counts: Record<string, number>; faculty: FundingFacultyRow[] };
type Options = { departments: string[]; funding_agencies: string[] };

const configuration: Record<Category, { title: string; singular: string; addPath: string; labels: Record<string, string>; financial: string[] }> = {
  SPONSORED_RESEARCH: {
    title: "Sponsored Research Projects", singular: "project", addPath: "/research-projects/new",
    labels: { total: "Total Proposals", submitted_under_review: "Submitted / Under Review", sanctioned: "Sanctioned Projects", ongoing: "Ongoing Projects", completed: "Completed Projects", sanctioned_amount: "Total Sanctioned Amount", faculty_contributors: "Faculty Contributors" },
    financial: ["sanctioned_amount"],
  },
  CONSULTANCY: {
    title: "Consultancy Projects", singular: "consultancy project", addPath: "/consultancy/new",
    labels: { total: "Total Consultancy Projects", ongoing: "Ongoing", completed: "Completed", contract_value: "Total Contract Value", amount_received: "Amount Received", faculty_contributors: "Faculty Contributors" },
    financial: ["contract_value", "amount_received"],
  },
  INTERNAL_GRANT: {
    title: "Seed Money / Internal Grants", singular: "internal grant", addPath: "/seed-money/new",
    labels: { total: "Total Internal Grants", faculty_beneficiaries: "Faculty Beneficiaries", sanctioned_amount: "Total Amount Sanctioned", amount_utilized: "Total Amount Utilized", completed: "Completed Grants" },
    financial: ["sanctioned_amount", "amount_utilized"],
  },
};

const awardedStatuses = new Set(["SANCTIONED", "ONGOING", "COMPLETED"]);
const financialMetrics = new Set(["sanctioned_amount", "contract_value", "amount_received", "amount_utilized"]);
const piRoles = new Set(["LEAD_PI", "MEMBER_PI", "ADMIN_PI", "PI"]);

function amount(value: string | number | null | undefined) {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(Number(value));
}

function investigatorRoleLabel(role: string) {
  if (role === "LEAD_PI") return "Lead PI";
  if (role === "MEMBER_PI") return "Member PI";
  if (role === "PI") return "Historical Principal Investigator";
  if (role === "CO_PI") return "Co-PI / Co-Investigator";
  if (role === "CO_INVESTIGATOR") return "Historical Co-Investigator";
  if (role === "ADMIN_PI") return "Administrative PI";
  if (role !== "BENEFICIARY") return role;
  return label(role);
}

function principalInvestigatorDisplay(record: FundingProject) {
  const investigators = record.faculty.filter((member) => piRoles.has(member.role));
  if (!investigators.length) return "Incomplete: no PI recorded";
  return investigators.map((member) => {
    const name = member.faculty_name || member.investigator_name;
    if (!name) return "Incomplete investigator record";
    return `${name} (${member.agency_role_label || investigatorRoleLabel(member.role)})`;
  }).join("; ");
}

function financialAmount(record: FundingProject, metric: string, category: Category) {
  if (!metric) {
    if (category === "SPONSORED_RESEARCH") return amount(awardedStatuses.has(record.status) ? record.sanctioned_amount : record.proposed_amount);
    if (!awardedStatuses.has(record.status)) return "—";
    return amount(category === "CONSULTANCY" ? record.contract_amount : record.sanctioned_amount);
  }
  if (!awardedStatuses.has(record.status)) return "—";
  if (metric === "contract_value") return amount(record.contract_amount);
  if (metric === "amount_received") return amount(record.amount_received);
  if (metric === "amount_utilized") return amount(record.amount_utilized);
  return amount(record.sanctioned_amount);
}

export default function FundingOverview({ category }: { category: Category }) {
  const searchParams = useSearchParams();
  const config = configuration[category];
  const facultyMetric = category === "INTERNAL_GRANT" ? "faculty_beneficiaries" : "faculty_contributors";
  const { range, ready } = useDateRange();
  const [masters, setMasters] = useState<Masters>();
  const [options, setOptions] = useState<Options>({ departments: [], funding_agencies: [] });
  const [result, setResult] = useState<PageResult>({ items: [], total: 0, page: 1, page_size: 25 });
  const [dashboard, setDashboard] = useState<Dashboard>({ totals: {}, role_counts: {}, faculty: [] });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [facultyId, setFacultyId] = useState(() => searchParams.get("faculty_id") || "");
  const [department, setDepartment] = useState("");
  const [agency, setAgency] = useState("");
  const [status, setStatus] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<RecordPageSize>(25);
  const [activeMetric, setActiveMetric] = useState("");
  const [showFaculty, setShowFaculty] = useState(false);
  const [revision, setRevision] = useState(0);

  const sharedParams = new URLSearchParams({
    ...range, category,
    ...(search ? { search } : {}), ...(facultyId ? { faculty_id: facultyId } : {}),
    ...(department ? { department } : {}), ...(agency ? { funding_agency: agency } : {}),
    ...(status ? { status } : {}), ...(includeInactive ? { include_inactive: "true" } : {}),
  });
  const listParams = new URLSearchParams(sharedParams);
  listParams.set("page", String(page));
  listParams.set("page_size", String(pageSize));
  if (activeMetric && activeMetric !== facultyMetric) listParams.set("metric", activeMetric);

  useEffect(() => {
    api<Masters>("/masters").then(setMasters).catch((reason: Error) => setError(reason.message));
    api<Options>("/funding-project-options").then(setOptions).catch((reason: Error) => setError(reason.message));
  }, []);
  useEffect(() => {
    if (!ready) return;
    setLoading(true); setError("");
    api<unknown>("/funding-projects?" + listParams)
      .then((data) => setResult(paginatedResult<FundingProject>(data, "Funding projects")))
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, [ready, range.from_date, range.to_date, category, search, facultyId, department, agency, status, includeInactive, page, pageSize, activeMetric, revision]);
  useEffect(() => {
    if (!ready) return;
    setDashboardLoading(true);
    api<Dashboard>("/funding-dashboard?" + sharedParams)
      .then(setDashboard)
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setDashboardLoading(false));
  }, [ready, range.from_date, range.to_date, category, search, facultyId, department, agency, status, includeInactive, revision]);

  function resetPage(change: () => void) {
    change(); setPage(1); setActiveMetric(""); setShowFaculty(false);
  }
  function resetFilters() {
    setSearch(""); setFacultyId(""); setDepartment(""); setAgency(""); setStatus("");
    setIncludeInactive(false); setPage(1); setActiveMetric(""); setShowFaculty(false);
  }
  function selectMetric(metric: string) {
    setActiveMetric(metric); setPage(1); setShowFaculty(metric === facultyMetric);
  }
  function viewFacultyProjects(identity: number) {
    setFacultyId(String(identity)); setActiveMetric(""); setShowFaculty(false); setPage(1);
    setTimeout(() => document.getElementById("funding-records")?.scrollIntoView({ behavior: "smooth" }), 0);
  }
  async function deactivate(id: number) {
    if (!confirm("Deactivate this funding record? Its Faculty links and evidence will be retained.")) return;
    try {
      await api(`/funding-projects/${id}`, { method: "DELETE" });
      if (result.items.length === 1 && page > 1) setPage(page - 1);
      else setRevision((value) => value + 1);
    } catch (reason) { setError((reason as Error).message); }
  }

  const financialDrillDown = financialMetrics.has(activeMetric);
  const amountHeading = activeMetric === "amount_received" ? "Amount received" : activeMetric === "amount_utilized" ? "Amount utilized" : activeMetric === "contract_value" ? "Contract / approved amount" : category === "SPONSORED_RESEARCH" ? "Proposed / sanctioned amount" : "Amount sanctioned";

  return <DashboardFrame>
    <ResearchPageHeader title={config.title} subtitle="Department funding records, lifecycle tracking, financial reporting and evidence.">
      <Link className="button" href={config.addPath}>+ Add {config.singular}</Link>
    </ResearchPageHeader>
    <DateRangeFilter />
    {error && <div className="error" role="alert">{error}</div>}
    <KpiGrid labels={config.labels} counts={dashboard.totals} loading={dashboardLoading} active={activeMetric} onSelect={selectMetric} financial={config.financial} />
    <p className="muted">Sanctioned and financial award totals include only sanctioned, ongoing, or completed records. Submitted and under-review proposal budgets remain stored but are not counted as awards.</p>

    {!activeMetric && <FacultyContributionTable
      title="Faculty funding contribution"
      columns={{ projects: "Distinct Funding Records", role_lead_pi: "Lead PI / Principal Investigator", role_member_pi: "Member PI", role_co_pi: "Co-PI / Co-Investigator", role_admin_pi: "Admin PI", role_beneficiary: "Beneficiary" }}
      rows={dashboard.faculty.map(({ department: _department, roles: _roles, ...row }) => row)}
      loading={dashboardLoading}
      note="One row per linked Faculty Master ID. Project totals stay distinct even when a Faculty member has several investigator roles."
      onSelect={(row) => viewFacultyProjects(row.id)}
    />}

    {showFaculty && <section className="panel" id="funding-faculty-contributors">
      <div className="row-between"><h2>{config.labels[facultyMetric]} · {dashboard.totals[facultyMetric] || 0}</h2><button className="secondary small" onClick={() => selectMetric("")}>Close drill-down</button></div>
      <p className="muted">One row per linked Faculty Master record. Manual investigators are excluded; each contributor’s project count is distinct.</p>
      {dashboardLoading ? <p role="status">Loading Faculty contributors…</p> : !dashboard.faculty.length ? <p className="dash-empty">No Faculty contributors match this selection.</p> : <div className="table-wrap"><table><thead><tr><th>Faculty</th><th>Employee ID</th><th>Department</th><th>Distinct projects</th><th>Investigator roles</th><th>Records</th></tr></thead><tbody>{dashboard.faculty.map((person) => <tr key={person.id}><td>{person.name}{person.is_active ? "" : " (historical)"}</td><td>{person.employee_id || "—"}</td><td>{person.department || "—"}</td><td>{person.projects}</td><td>{person.roles.map(investigatorRoleLabel).join(", ") || "—"}</td><td><button className="link-button" onClick={() => viewFacultyProjects(person.id)}>View matching project records</button></td></tr>)}</tbody></table></div>}
    </section>}

    {!showFaculty && <>
      <section className="panel"><h2>Find {config.title.toLowerCase()}</h2><div className="filters">
        <label className="field">Search<input value={search} placeholder="Title, agency, department, or Faculty" onChange={(event) => resetPage(() => setSearch(event.target.value))} /></label>
        <label className="field">Faculty<select value={facultyId} onChange={(event) => resetPage(() => setFacultyId(event.target.value))}><option value="">All Faculty</option>{masters?.faculty.map((person) => <option key={person.id} value={person.id}>{person.name}{person.is_active ? "" : " (historical)"}</option>)}</select></label>
        <label className="field">Department<select value={department} onChange={(event) => resetPage(() => setDepartment(event.target.value))}><option value="">All departments</option>{options.departments.map((value) => <option key={value}>{value}</option>)}</select></label>
        <label className="field">Funding agency / client<select value={agency} onChange={(event) => resetPage(() => setAgency(event.target.value))}><option value="">All agencies / clients</option>{options.funding_agencies.map((value) => <option key={value}>{value}</option>)}</select></label>
        <label className="field">Status<select value={status} onChange={(event) => resetPage(() => setStatus(event.target.value))}><option value="">All statuses</option>{["DRAFT", "SUBMITTED", "UNDER_REVIEW", "SANCTIONED", "ONGOING", "COMPLETED", "REJECTED", "WITHDRAWN"].map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></label>
        <label className="field">Record status<span className="check"><input type="checkbox" checked={includeInactive} onChange={(event) => resetPage(() => setIncludeInactive(event.target.checked))} />Include inactive</span></label>
        <div className="actions"><button type="button" className="secondary" onClick={resetFilters}>Reset filters</button></div>
      </div></section>

      <section className="panel" id="funding-records"><div className="row-between"><h2>{activeMetric ? config.labels[activeMetric] : config.title} · {result.total}</h2>{activeMetric && <button className="secondary small" onClick={() => selectMetric("")}>Clear KPI selection</button>}</div>
        {financialDrillDown && <p className="muted">Only sanctioned, ongoing, or completed records with the corresponding amount contribute to this financial total.</p>}
        {loading ? <p role="status">Loading funding records…</p> : !result.items.length ? <p className="dash-empty">No records match the current filters.</p> : <div className="table-wrap"><table><thead><tr><th>Project</th><th>Agency / client</th><th>PI</th><th>Reporting date</th><th>Status</th><th>{amountHeading}</th><th>Actions</th></tr></thead><tbody>{result.items.map((record) => <tr key={record.id}><td><strong>{record.title}</strong><small>{record.department}</small></td><td>{record.funding_agency || "—"}</td><td>{principalInvestigatorDisplay(record)}</td><td>{record.sanction_date || record.proposal_submission_date || record.start_date || "—"}</td><td>{label(record.status)}</td><td>{financialAmount(record, activeMetric, category)}</td><td className="actions"><Link href={`/funding-projects/${record.id}`}>View</Link><Link href={`/funding-projects/${record.id}/edit`}>Edit</Link>{(record as FundingProject & { is_active: boolean }).is_active && <button className="danger small" onClick={() => deactivate(record.id!)}>Deactivate</button>}</td></tr>)}</tbody></table></div>}
        <PaginationControls page={result.page} pageSize={pageSize} total={result.total} loading={loading} onPageChange={setPage} onPageSizeChange={(next) => { setPageSize(next); setPage(1); }} />
      </section>
    </>}
  </DashboardFrame>;
}
