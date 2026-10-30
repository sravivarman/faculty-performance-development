"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import DateRangeFilter, { useDateRange } from "@/components/DateRange";
import { api, label, Masters, paginatedResult } from "@/lib/api";
import { DashboardFrame, KpiGrid, ResearchPageHeader } from "@/components/dashboard/UI";
import { Distribution, SeriesChart } from "@/components/dashboard/Charts";
import FacultyContributionTable from "@/components/dashboard/FacultyContributionTable";
import FacultySelector from "@/components/FacultySelector";
import PaginationControls, { RecordPageSize } from "@/components/PaginationControls";

type Row = {
  id: number;
  faculty_id: number;
  faculty_name: string;
  name: string;
  provider: string;
  category: string;
  status: string;
  completion_date?: string;
  is_active: boolean;
};

type Result = { items: Row[]; total: number; page: number; page_size: number | "all" };
type Trend = { month: string; completed: number; nptel_swayam: number; mooc: number; other: number };
type Provider = { provider: string; completed: number };
type FacultyPerformance = { id: number; name: string; employee_id?: string | null; completed: number; nptel_swayam: number; mooc: number; other: number; in_progress: number };
type Dashboard = { totals: Record<string, number>; categories: Record<string, number>; trend: Trend[]; providers: Provider[]; faculty_performance: FacultyPerformance[] };
type Drilldown = "" | "certifications" | "completed" | "in_progress" | "nptel_swayam" | "mooc" | "other" | "faculty";

const categories = ["NPTEL_SWAYAM", "MOOC", "OTHER"];
const categoryLabels: Record<string, string> = { NPTEL_SWAYAM: "NPTEL / SWAYAM", MOOC: "MOOC", OTHER: "Other Certifications" };

export default function Page() {
  const { range, ready } = useDateRange();
  const searchParams = useSearchParams();
  const [masters, setMasters] = useState<Masters>();
  const [result, setResult] = useState<Result>({ items: [], total: 0, page: 1, page_size: 25 });
  const [dashboard, setDashboard] = useState<Dashboard>({ totals: {}, categories: {}, trend: [], providers: [], faculty_performance: [] });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [faculty, setFaculty] = useState(() => searchParams.get("faculty_id") || "");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState(() => searchParams.get("status") || "");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [currentInProgress, setCurrentInProgress] = useState(() => searchParams.get("current_in_progress") === "true");
  const [drilldown, setDrilldown] = useState<Drilldown>("");
  const [showFacultyContributors, setShowFacultyContributors] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<RecordPageSize>(25);

  // KPI selection is intentionally separate from the normal overview filters.
  // It narrows only the contributing-record list and must never alter the
  // request that supplies the summary cards.
  const drillCategory = drilldown === "nptel_swayam"
    ? "NPTEL_SWAYAM"
    : drilldown === "mooc"
      ? "MOOC"
      : drilldown === "other"
        ? "OTHER"
        : "";
  const drillStatus = drilldown === "in_progress"
    ? "IN_PROGRESS"
    : ["certifications", "completed", "nptel_swayam", "mooc", "other"].includes(drilldown)
      ? "COMPLETED"
      : "";
  const recordCategory = drillCategory || category;
  const recordStatus = drillStatus || status;
  const recordCurrentInProgress = drilldown ? drilldown === "in_progress" : currentInProgress;

  const listParams = new URLSearchParams({
    ...range, page: String(page), page_size: String(pageSize),
    ...(search ? { search } : {}), ...(faculty ? { faculty_id: faculty } : {}),
    ...(recordCategory ? { category: recordCategory } : {}), ...(recordStatus ? { status: recordStatus } : {}),
    ...(includeInactive ? { include_inactive: "true" } : {}),
    ...(recordCurrentInProgress ? { current_in_progress: "true" } : {}),
  });
  const dashboardParams = new URLSearchParams({
    ...range, ...(search ? { search } : {}), ...(faculty ? { faculty_id: faculty } : {}),
    ...(category ? { category } : {}), ...(status ? { status } : {}),
    ...(includeInactive ? { include_inactive: "true" } : {}),
  });

  const loadList = () => {
    if (!ready) return;
    setLoading(true);
    setError("");
    api<unknown>("/certifications?" + listParams)
      .then((data) => setResult(paginatedResult<Row>(data, "Certifications")))
      .catch((requestError: Error) => setError(requestError.message))
      .finally(() => setLoading(false));
  };
  const loadDashboard = () => {
    if (!ready) return;
    setDashboardLoading(true);
    api<Dashboard>("/certification-dashboard?" + dashboardParams)
      .then(setDashboard)
      .catch((requestError: Error) => setError(requestError.message))
      .finally(() => setDashboardLoading(false));
  };

  useEffect(() => {
    api<Masters>("/masters").then(setMasters).catch((requestError: Error) => setError(requestError.message));
  }, []);
  useEffect(() => { loadList(); }, [
    ready, range.from_date, range.to_date, page, pageSize, search, faculty, category, status, includeInactive, currentInProgress, drilldown,
  ]);
  useEffect(() => { loadDashboard(); }, [
    ready, range.from_date, range.to_date, search, faculty, category, status, includeInactive,
  ]);

  const resetPage = (change: () => void) => {
    change();
    setPage(1);
    setDrilldown("");
    setShowFacultyContributors(false);
  };
  const resetFilters = () => {
    setSearch(""); setFaculty(""); setCategory(""); setStatus("");
    setIncludeInactive(false); setCurrentInProgress(false); setDrilldown(""); setShowFacultyContributors(false); setPage(1);
  };
  const selectKpi = (selected: Drilldown) => {
    setPage(1);
    setDrilldown(selected);
    setShowFacultyContributors(selected === "faculty");
    if (!selected) {
      setTimeout(() => document.getElementById("certification-records")?.scrollIntoView({ behavior: "smooth" }), 0);
      return;
    }
    if (selected === "in_progress") {
      setTimeout(() => document.getElementById("certification-records")?.scrollIntoView({ behavior: "smooth" }), 0);
      return;
    }
    setTimeout(() => document.getElementById(selected === "faculty" ? "certification-faculty-contributors" : "certification-records")?.scrollIntoView({ behavior: "smooth" }), 0);
  };
  const selectCategory = (value: string) => selectKpi(({ NPTEL_SWAYAM: "nptel_swayam", MOOC: "mooc", OTHER: "other" }[value] || "") as Drilldown);

  async function deactivate(id: number) {
    if (!confirm("Deactivate this certification?")) return;
    try {
      await api("/certifications/" + id, { method: "DELETE" });
      if (result.items.length === 1 && page > 1) setPage(page - 1);
      else loadList();
      loadDashboard();
    } catch (requestError) {
      setError((requestError as Error).message);
    }
  }
  const kpiCounts = {
    ...dashboard.totals,
    nptel_swayam: dashboard.categories.NPTEL_SWAYAM,
    mooc: dashboard.categories.MOOC,
    other: dashboard.categories.OTHER,
    faculty: dashboard.totals.faculty_contributors,
  };
  const drilldownMessage = drilldown === "in_progress"
    ? "Showing in-progress certifications. Current work is not filtered by completion date."
    : drilldown === "faculty"
      ? "Showing completed certifications in the selected period; the KPI above counts distinct Faculty members."
      : "";
  const viewFacultyCertifications = (identity: number) => {
    setFaculty(String(identity));
    setPage(1);
    setDrilldown("");
    setShowFacultyContributors(false);
    setTimeout(() => document.getElementById("certification-records")?.scrollIntoView({ behavior: "smooth" }), 0);
  };

  return (
    <DashboardFrame>
      <ResearchPageHeader title="Certifications / MOOCs" subtitle="Department certification records, outcomes, and current learning work.">
        <Link className="button" href="/certifications/new">+ Add certification</Link>
      </ResearchPageHeader>
      <DateRangeFilter />
      {error && <div className="error" role="alert">{error}</div>}
      <KpiGrid
        labels={{
          certifications: "Certifications completed in period",
          completed: "Completed",
          in_progress: "In progress",
          nptel_swayam: "NPTEL / SWAYAM",
          mooc: "MOOCs",
          other: "Other certifications",
          faculty: "Faculty certified",
        }}
        counts={kpiCounts}
        loading={dashboardLoading}
        active={drilldown}
        onSelect={(key) => selectKpi(key as Drilldown)}
      />
      <p className="muted">
        Completion and category cards use the selected inclusive completion-date period. In-progress work is active current work and is independent of that period.
      </p>
      <div className="dash-charts">
        <Distribution title="Completed certification distribution" labels={{ NPTEL_SWAYAM: "NPTEL / SWAYAM", MOOC: "MOOC", OTHER: "Other Certifications" }} counts={dashboard.categories} onSelect={selectCategory} loading={dashboardLoading} note="Completed records within the selected inclusive completion-date period." />
        <Distribution title="Certification status summary" labels={{ completed: "Completed in period", in_progress: "Current in progress" }} counts={{ completed: dashboard.totals.completed || 0, in_progress: dashboard.totals.in_progress || 0 }} onSelect={(value) => selectKpi(value as Drilldown)} loading={dashboardLoading} note="Current in-progress work is independent of the completion-date period." />
        <SeriesChart title="Completion trend" rows={dashboard.trend} series={{ completed: "Completed", nptel_swayam: "NPTEL / SWAYAM", mooc: "MOOC", other: "Other" }} loading={dashboardLoading} note="Monthly completed certifications by completion date. Null completion dates are excluded." />
      </div>
      <section className="panel"><h2>Provider analysis</h2><p className="muted">Providers use stored labels; spelling variants are not merged automatically.</p>{dashboardLoading ? <p role="status">Loading providers…</p> : !dashboard.providers.length ? <p className="dash-empty">No completed providers in this selection.</p> : <div className="table-wrap"><table><thead><tr><th>Provider</th><th>Completed certifications</th></tr></thead><tbody>{dashboard.providers.map((provider) => <tr key={provider.provider}><td>{provider.provider}</td><td>{provider.completed}</td></tr>)}</tbody></table></div>}</section>
      <FacultyContributionTable title="Faculty certification performance" columns={{ completed: "Completed", nptel_swayam: "NPTEL / SWAYAM", mooc: "MOOC", other: "Other", in_progress: "Current In Progress" }} rows={dashboard.faculty_performance} loading={dashboardLoading} note="Completed metrics use the selected inclusive completion-date period; current in-progress records are active work." />

      {showFacultyContributors && <section className="panel" id="certification-faculty-contributors">
        <div className="row-between"><h2>Faculty certified · {dashboard.totals.faculty_contributors || 0}</h2><button className="secondary small" onClick={() => selectKpi("")}>Close drill-down</button></div>
        <p className="muted">One row per Faculty Master record with a completed certification in the selected inclusive completion-date period.</p>
        {dashboardLoading ? <p role="status">Loading Faculty contributors…</p> : !dashboard.faculty_performance.length ? <p className="dash-empty">No Faculty contributors match this selection.</p> : <div className="table-wrap"><table><thead><tr><th>Faculty</th><th>Completed certifications</th><th>Records</th></tr></thead><tbody>{dashboard.faculty_performance.map((person) => <tr key={person.id}><td>{person.name}<small>{person.employee_id || "—"}</small></td><td>{person.completed}</td><td><button className="link-button" onClick={() => viewFacultyCertifications(person.id)}>View matching certifications</button></td></tr>)}</tbody></table></div>}
      </section>}

      <section className="panel">
        <h2>Find certifications</h2>
        <div className="filters">
          <label className="field">
            Search
            <input
              placeholder="Faculty, certification, or provider"
              value={search}
              onChange={(event) => resetPage(() => setSearch(event.target.value))}
            />
          </label>
          <label className="field">
            Faculty
            <select value={faculty} onChange={(event) => resetPage(() => setFaculty(event.target.value))}>
              <option value="">All Faculty</option>
              {masters?.faculty.map((person) => <option key={person.id} value={person.id}>{person.name}{person.is_active ? "" : " (historical)"}</option>)}
            </select>
          </label>
          <label className="field">
            Category
            <select value={category} onChange={(event) => resetPage(() => setCategory(event.target.value))}>
              <option value="">All categories</option>
              {categories.map((value) => <option key={value} value={value}>{categoryLabels[value]}</option>)}
            </select>
          </label>
          <label className="field">
            Status
            <select
              value={status}
              onChange={(event) => {
                const nextStatus = event.target.value;
                resetPage(() => {
                  setStatus(nextStatus);
                  setCurrentInProgress(nextStatus === "IN_PROGRESS");
                });
              }}
            >
              <option value="">All statuses</option>
              <option value="COMPLETED">Completed</option>
              <option value="IN_PROGRESS">In progress</option>
            </select>
          </label>
          <label className="field">
            Record status
            <span className="check"><input type="checkbox" checked={includeInactive} onChange={(event) => resetPage(() => setIncludeInactive(event.target.checked))} />Include inactive</span>
          </label>
          <div className="actions"><button type="button" className="secondary" onClick={resetFilters}>Reset filters</button></div>
        </div>
      </section>

      <section className="panel" id="certification-records">
        <div className="row-between">
          <h2>{drilldown ? ({ certifications: "Certifications", completed: "Completed certifications", in_progress: "In-progress certifications", nptel_swayam: "NPTEL / SWAYAM certifications", mooc: "MOOC certifications", other: "Other certifications", faculty: "Faculty certifications" }[drilldown] || "Certifications") : "Certifications"} · {result.total}</h2>
          {drilldown && <button className="secondary small" onClick={() => selectKpi("")}>Clear KPI selection</button>}
        </div>
        {drilldownMessage && <p className="muted">{drilldownMessage}</p>}
        {loading ? <p role="status">Loading certifications…</p> : !result.items.length ? (
          <p className="dash-empty">No certifications match the current filters.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Certification</th><th>Faculty</th><th>Status</th><th>Completion</th><th>Actions</th></tr>
              </thead>
              <tbody>
                {result.items.map((row) => (
                  <tr key={row.id}>
                    <td><strong>{row.name}</strong><small>{row.provider} · {categoryLabels[row.category] || label(row.category)}</small></td>
                    <td>{row.faculty_name}</td>
                    <td>{label(row.status)} · {row.is_active ? "Active" : "Inactive"}</td>
                    <td>{row.completion_date || "—"}</td>
                    <td className="actions">
                      <Link href={"/certifications/" + row.id}>View</Link>
                      <Link href={"/certifications/" + row.id + "/edit"}>Edit</Link>
                      {row.is_active && <button className="danger small" onClick={() => deactivate(row.id)}>Deactivate</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <PaginationControls page={result.page} pageSize={pageSize} total={result.total} loading={loading} onPageChange={setPage} onPageSizeChange={(next) => { setPageSize(next); setPage(1); }} />
      </section>

    </DashboardFrame>
  );
}
