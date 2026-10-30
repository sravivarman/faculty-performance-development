"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import DateRangeFilter, { useDateRange } from "@/components/DateRange";
import FacultyContributionTable from "@/components/dashboard/FacultyContributionTable";
import { DashboardFrame, KpiGrid, ResearchPageHeader } from "@/components/dashboard/UI";
import PaginationControls, { RecordPageSize } from "@/components/PaginationControls";
import { api, label, Masters, paginatedResult } from "@/lib/api";
import { FundingProject } from "@/components/FundingEditor";

type Category = "SPONSORED_RESEARCH" | "CONSULTANCY" | "INTERNAL_GRANT";
type PageResult = { items: FundingProject[]; total: number; page: number; page_size: number | "all" };
type Dashboard = { totals: Record<string, number>; faculty: { id: number; name: string; employee_id?: string | null; is_active: boolean; projects: number }[] };
type Options = { departments: string[]; funding_agencies: string[] };

const configuration: Record<Category, { title: string; singular: string; addPath: string; labels: Record<string, string>; financial: string[] }> = {
  SPONSORED_RESEARCH: { title: "Sponsored Research Projects", singular: "project", addPath: "/research-projects/new", labels: { total: "Total Proposals", submitted_under_review: "Submitted / Under Review", sanctioned: "Sanctioned Projects", ongoing: "Ongoing Projects", completed: "Completed Projects", sanctioned_amount: "Total Sanctioned Amount" }, financial: ["sanctioned_amount"] },
  CONSULTANCY: { title: "Consultancy Projects", singular: "consultancy project", addPath: "/consultancy/new", labels: { total: "Total Consultancy Projects", ongoing: "Ongoing", completed: "Completed", contract_value: "Total Contract Value", amount_received: "Amount Received" }, financial: ["contract_value", "amount_received"] },
  INTERNAL_GRANT: { title: "Seed Money / Internal Grants", singular: "internal grant", addPath: "/seed-money/new", labels: { total: "Total Internal Grants", faculty_beneficiaries: "Faculty Beneficiaries", sanctioned_amount: "Total Amount Sanctioned", amount_utilized: "Total Amount Utilized", completed: "Completed Grants" }, financial: ["sanctioned_amount", "amount_utilized"] },
};

function amount(value: string | number | null | undefined) {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(Number(value));
}

export default function FundingOverview({ category }: { category: Category }) {
  const config = configuration[category];
  const { range, ready } = useDateRange();
  const [masters, setMasters] = useState<Masters>();
  const [options, setOptions] = useState<Options>({ departments: [], funding_agencies: [] });
  const [result, setResult] = useState<PageResult>({ items: [], total: 0, page: 1, page_size: 25 });
  const [dashboard, setDashboard] = useState<Dashboard>({ totals: {}, faculty: [] });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [facultyId, setFacultyId] = useState("");
  const [department, setDepartment] = useState("");
  const [agency, setAgency] = useState("");
  const [status, setStatus] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<RecordPageSize>(25);
  const [activeMetric, setActiveMetric] = useState("");
  const [showFaculty, setShowFaculty] = useState(false);
  const [revision, setRevision] = useState(0);

  const sharedParams = new URLSearchParams({ ...range, category, ...(search ? { search } : {}), ...(facultyId ? { faculty_id: facultyId } : {}), ...(department ? { department } : {}), ...(agency ? { funding_agency: agency } : {}), ...(status ? { status } : {}), ...(includeInactive ? { include_inactive: "true" } : {}) });
  const listParams = new URLSearchParams(sharedParams);
  listParams.set("page", String(page));
  listParams.set("page_size", String(pageSize));
  if (activeMetric && activeMetric !== "faculty_beneficiaries") listParams.set("metric", activeMetric);

  useEffect(() => { api<Masters>("/masters").then(setMasters).catch((reason: Error) => setError(reason.message)); api<Options>("/funding-project-options").then(setOptions).catch((reason: Error) => setError(reason.message)); }, []);
  useEffect(() => {
    if (!ready) return;
    setLoading(true); setError("");
    api<unknown>("/funding-projects?" + listParams).then((data) => setResult(paginatedResult<FundingProject>(data, "Funding projects"))).catch((reason: Error) => setError(reason.message)).finally(() => setLoading(false));
  }, [ready, range.from_date, range.to_date, category, search, facultyId, department, agency, status, includeInactive, page, pageSize, activeMetric, revision]);
  useEffect(() => {
    if (!ready) return;
    setDashboardLoading(true);
    api<Dashboard>("/funding-dashboard?" + sharedParams).then(setDashboard).catch((reason: Error) => setError(reason.message)).finally(() => setDashboardLoading(false));
  }, [ready, range.from_date, range.to_date, category, search, facultyId, department, agency, status, includeInactive, revision]);

  function resetPage(change: () => void) { change(); setPage(1); setActiveMetric(""); setShowFaculty(false); }
  function resetFilters() { setSearch(""); setFacultyId(""); setDepartment(""); setAgency(""); setStatus(""); setIncludeInactive(false); setPage(1); setActiveMetric(""); setShowFaculty(false); }
  function selectMetric(metric: string) { setActiveMetric(metric); setPage(1); setShowFaculty(metric === "faculty_beneficiaries"); }
  async function deactivate(id: number) {
    if (!confirm("Deactivate this funding record? Its Faculty links and evidence will be retained.")) return;
    try { await api(`/funding-projects/${id}`, { method: "DELETE" }); if (result.items.length === 1 && page > 1) setPage(page - 1); else setRevision((value) => value + 1); } catch (reason) { setError((reason as Error).message); }
  }

  return <DashboardFrame>
    <ResearchPageHeader title={config.title} subtitle="Department funding records, lifecycle tracking, financial reporting and evidence."><Link className="button" href={config.addPath}>+ Add {config.singular}</Link></ResearchPageHeader>
    <DateRangeFilter />
    {error && <div className="error" role="alert">{error}</div>}
    <KpiGrid labels={config.labels} counts={dashboard.totals} loading={dashboardLoading} active={activeMetric} onSelect={selectMetric} financial={config.financial} />
    {showFaculty && <FacultyContributionTable title="Faculty beneficiaries" columns={{ projects: "Distinct Funding Records" }} rows={dashboard.faculty} loading={dashboardLoading} note="One row per Faculty Master ID. Counts are distinct funding records, not association rows." onSelect={(row) => { setFacultyId(String(row.id)); setActiveMetric(""); setShowFaculty(false); setPage(1); }} />}
    <section className="panel"><h2>Find {config.title.toLowerCase()}</h2><div className="filters">
      <label className="field">Search<input value={search} placeholder="Title, agency, department, or Faculty" onChange={(event) => resetPage(() => setSearch(event.target.value))} /></label>
      <label className="field">Faculty<select value={facultyId} onChange={(event) => resetPage(() => setFacultyId(event.target.value))}><option value="">All Faculty</option>{masters?.faculty.map((person) => <option key={person.id} value={person.id}>{person.name}{person.is_active ? "" : " (historical)"}</option>)}</select></label>
      <label className="field">Department<select value={department} onChange={(event) => resetPage(() => setDepartment(event.target.value))}><option value="">All departments</option>{options.departments.map((value) => <option key={value}>{value}</option>)}</select></label>
      <label className="field">Funding agency / client<select value={agency} onChange={(event) => resetPage(() => setAgency(event.target.value))}><option value="">All agencies / clients</option>{options.funding_agencies.map((value) => <option key={value}>{value}</option>)}</select></label>
      <label className="field">Status<select value={status} onChange={(event) => resetPage(() => setStatus(event.target.value))}><option value="">All statuses</option>{["DRAFT", "SUBMITTED", "UNDER_REVIEW", "SANCTIONED", "ONGOING", "COMPLETED", "REJECTED", "WITHDRAWN"].map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></label>
      <label className="field">Record status<span className="check"><input type="checkbox" checked={includeInactive} onChange={(event) => resetPage(() => setIncludeInactive(event.target.checked))} />Include inactive</span></label>
      <div className="actions"><button type="button" className="secondary" onClick={resetFilters}>Reset filters</button></div>
    </div></section>
    <section className="panel"><div className="row-between"><h2>{activeMetric ? config.labels[activeMetric] : config.title} · {result.total}</h2>{activeMetric && <button className="secondary small" onClick={() => selectMetric("")}>Clear KPI selection</button>}</div>
      {loading ? <p role="status">Loading funding records…</p> : !result.items.length ? <p className="dash-empty">No records match the current filters.</p> : <div className="table-wrap"><table><thead><tr><th>Project</th><th>Agency / client</th><th>PI</th><th>Reporting date</th><th>Status</th><th>Sanctioned amount</th><th>Actions</th></tr></thead><tbody>{result.items.map((record) => { const pi = record.faculty.find((member) => member.role === "PI"); return <tr key={record.id}><td><strong>{record.title}</strong><small>{record.department}</small></td><td>{record.funding_agency || "—"}</td><td>{pi?.faculty_name || "—"}</td><td>{record.sanction_date || record.proposal_submission_date || record.start_date || "—"}</td><td>{label(record.status)}</td><td>{amount(record.sanctioned_amount)}</td><td className="actions"><Link href={`/funding-projects/${record.id}`}>View</Link><Link href={`/funding-projects/${record.id}/edit`}>Edit</Link>{(record as FundingProject & { is_active: boolean }).is_active && <button className="danger small" onClick={() => deactivate(record.id!)}>Deactivate</button>}</td></tr>; })}</tbody></table></div>}
      <PaginationControls page={result.page} pageSize={pageSize} total={result.total} loading={loading} onPageChange={setPage} onPageSizeChange={(next) => { setPageSize(next); setPage(1); }} />
    </section>
  </DashboardFrame>;
}
