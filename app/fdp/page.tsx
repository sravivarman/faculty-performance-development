"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import DateRangeFilter, { useDateRange } from "@/components/DateRange";
import { api, label, Masters, paginatedResult } from "@/lib/api";
import { DashboardFrame, KpiGrid, ResearchPageHeader } from "@/components/dashboard/UI";
import { Distribution, SeriesChart } from "@/components/dashboard/Charts";
import FacultyContributionTable from "@/components/dashboard/FacultyContributionTable";
import PaginationControls, { RecordPageSize } from "@/components/PaginationControls";

type Row = {
  id: number;
  title: string;
  activity_type: string;
  organizing_institution: string;
  start_date: string;
  end_date?: string;
  is_active: boolean;
  participants: { faculty_id: number; role: string; faculty_name: string }[];
};

type PageResult = { items: Row[]; total: number; page: number; page_size: number | "all" };
type FacultyParticipant = { id: number; name: string; is_active: boolean; activity_count: number };
type Trend = { month: string; activities: number; fdp: number; workshops: number; sttp: number };
type FacultyPerformance = FacultyParticipant & { employee_id?: string | null; participations: number; role_attendee: number; role_coordinator: number; role_resource_person: number; type_fdp: number; type_workshop: number; type_sttp: number };
type Dashboard = { totals: Record<string, number>; types: Record<string, number>; role_counts: Record<string, number>; trend: Trend[]; faculty_performance: FacultyPerformance[]; faculty_participants: FacultyParticipant[] };

const roles = ["ATTENDEE", "RESOURCE_PERSON", "COORDINATOR"];
const types = ["FDP", "STTP", "WORKSHOP", "WEBINAR", "SEMINAR", "INTERNSHIP", "INDUSTRIAL_TRAINING"];
const activityTypeLabels: Record<string, string> = { FDP: "FDP", STTP: "STTP", WORKSHOP: "Workshop", WEBINAR: "Webinar", SEMINAR: "Seminar", INTERNSHIP: "Internship", INDUSTRIAL_TRAINING: "Industrial Training" };
const kpiLabels: Record<string, string> = { activities: "Distinct Activities", fdp: "FDPs", sttp: "STTPs", workshops: "Workshops", webinars: "Webinars", seminars: "Seminars", internships: "Internships", industrial_training: "Industrial Training" };
const kpiTypes: Record<string, string> = { fdp: "FDP", sttp: "STTP", workshops: "WORKSHOP", webinars: "WEBINAR", seminars: "SEMINAR", internships: "INTERNSHIP", industrial_training: "INDUSTRIAL_TRAINING" };

export default function Page() {
  const { range, ready } = useDateRange();
  const [masters, setMasters] = useState<Masters>();
  const [result, setResult] = useState<PageResult>({ items: [], total: 0, page: 1, page_size: 25 });
  const [dashboard, setDashboard] = useState<Dashboard>({ totals: {}, types: {}, role_counts: {}, trend: [], faculty_performance: [], faculty_participants: [] });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [activityType, setActivityType] = useState("");
  const [activityGroup, setActivityGroup] = useState("");
  const [facultyId, setFacultyId] = useState("");
  const [role, setRole] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<RecordPageSize>(25);
  const [activeMetric, setActiveMetric] = useState("");
  const [showFacultyParticipants, setShowFacultyParticipants] = useState(false);

  // The dashboard scope deliberately excludes `activeMetric`. A KPI click is a
  // record drill-down, not a change to the overview filters that define the
  // KPI values.
  const drillActivityType = kpiTypes[activeMetric] || "";
  const recordActivityType = drillActivityType || activityType;

  const listParams = new URLSearchParams({
    ...range,
    page: String(page),
    page_size: String(pageSize),
    ...(search ? { search } : {}),
    ...(recordActivityType ? { activity_type: recordActivityType } : {}),
    ...(activityGroup ? { activity_group: activityGroup } : {}),
    ...(facultyId ? { faculty_id: facultyId } : {}),
    ...(role ? { role } : {}),
    ...(includeInactive ? { include_inactive: "true" } : {}),
  });
  const dashboardParams = new URLSearchParams({
    ...range,
    ...(search ? { search } : {}),
    ...(activityType ? { activity_type: activityType } : {}),
    ...(activityGroup ? { activity_group: activityGroup } : {}),
    ...(facultyId ? { faculty_id: facultyId } : {}),
    ...(role ? { role } : {}),
    ...(includeInactive ? { include_inactive: "true" } : {}),
  });

  const loadList = () => {
    if (!ready) return;
    setLoading(true);
    setError("");
    api<unknown>("/fdp-activities?" + listParams)
      .then((data) => setResult(paginatedResult<Row>(data, "FDP activities")))
      .catch((requestError: Error) => setError(requestError.message))
      .finally(() => setLoading(false));
  };
  const loadDashboard = () => {
    if (!ready) return;
    setDashboardLoading(true);
    api<Dashboard>("/fdp-dashboard?" + dashboardParams)
      .then(setDashboard)
      .catch((requestError: Error) => setError(requestError.message))
      .finally(() => setDashboardLoading(false));
  };

  useEffect(() => {
    api<Masters>("/masters").then(setMasters).catch((requestError: Error) => setError(requestError.message));
  }, []);
  useEffect(() => {
    loadList();
  }, [ready, range.from_date, range.to_date, page, pageSize, search, activityType, activityGroup, facultyId, role, includeInactive, activeMetric]);
  useEffect(() => {
    loadDashboard();
  }, [ready, range.from_date, range.to_date, search, activityType, activityGroup, facultyId, role, includeInactive]);

  const resetPage = (change: () => void) => {
    change();
    setPage(1);
    setActiveMetric("");
    setShowFacultyParticipants(false);
  };
  const resetFilters = () => {
    setSearch(""); setActivityType(""); setActivityGroup(""); setFacultyId("");
    setRole(""); setIncludeInactive(false); setPage(1);
    setActiveMetric(""); setShowFacultyParticipants(false);
  };
  const selectMetric = (metric: string) => {
    setActiveMetric(metric);
    setShowFacultyParticipants(false);
    setPage(1);
    if (metric === "faculty_contributors") {
      setShowFacultyParticipants(true);
      setTimeout(() => document.getElementById("faculty-participants")?.scrollIntoView({ behavior: "smooth" }), 0);
    }
    if (metric !== "faculty_contributors") setTimeout(() => document.getElementById("fdp-records")?.scrollIntoView({ behavior: "smooth" }), 0);
  };
  const viewFacultyActivities = (identity: number) => {
    setFacultyId(String(identity));
    setActivityGroup("");
    setPage(1);
    setActiveMetric("");
    setShowFacultyParticipants(false);
    setTimeout(() => document.getElementById("fdp-records")?.scrollIntoView({ behavior: "smooth" }), 0);
  };
  const viewFacultyPerformance = (identity: number, key: string) => {
    setFacultyId(String(identity));
    setRole(key.startsWith("role_") ? key.slice(5).toUpperCase() : "");
    setActivityType(key.startsWith("type_") ? key.slice(5).toUpperCase() : "");
    setActivityGroup(""); setPage(1); setActiveMetric(""); setShowFacultyParticipants(false);
    setTimeout(() => document.getElementById("fdp-records")?.scrollIntoView({ behavior: "smooth" }), 0);
  };
  const selectActivityType = (value: string) => { setActivityType(value); setActivityGroup(""); setPage(1); setActiveMetric(""); setShowFacultyParticipants(false); };
  const selectRole = (value: string) => { setRole(value); setPage(1); setActiveMetric(""); setShowFacultyParticipants(false); };

  async function deactivate(id: number) {
    if (!confirm("Deactivate this activity?")) return;
    try {
      await api("/fdp-activities/" + id, { method: "DELETE" });
      if (result.items.length === 1 && page > 1) setPage(page - 1);
      else loadList();
      loadDashboard();
    } catch (requestError) {
      setError((requestError as Error).message);
    }
  }
  const kpiCounts = {
    activities: dashboard.totals.activities,
    fdp: dashboard.types.FDP,
    sttp: dashboard.types.STTP,
    workshops: dashboard.types.WORKSHOP,
    webinars: dashboard.types.WEBINAR,
    seminars: dashboard.types.SEMINAR,
    internships: dashboard.types.INTERNSHIP,
    industrial_training: dashboard.types.INDUSTRIAL_TRAINING,
  };
  return (
    <DashboardFrame>
      <ResearchPageHeader title="Faculty Development Activities" subtitle="Coordinator entry, participation, and activity management.">
        <Link className="button" href="/fdp/new">+ Add activity</Link>
      </ResearchPageHeader>
      <DateRangeFilter />
      {error && <div className="error" role="alert">{error}</div>}
      <KpiGrid
        labels={kpiLabels}
        counts={kpiCounts}
        loading={dashboardLoading}
        active={activeMetric}
        onSelect={selectMetric}
      />
      <div className="dash-charts">
        <Distribution title="Activity distribution" labels={activityTypeLabels} counts={dashboard.types} onSelect={selectActivityType} loading={dashboardLoading} note="Distinct activities in the selected inclusive start-date period." />
        <Distribution title="Participation by role" labels={Object.fromEntries(roles.map((value) => [value, label(value)]))} counts={dashboard.role_counts} onSelect={selectRole} loading={dashboardLoading} note="Faculty participation associations. One Faculty may hold more than one role in an activity." />
        <SeriesChart title="Activity trend" rows={dashboard.trend} series={{ activities: "Activities", fdp: "FDPs", workshops: "Workshops", sttp: "STTPs" }} loading={dashboardLoading} note="Monthly distinct activity totals by start date." />
      </div>
      <FacultyContributionTable title="Faculty development performance" columns={{ activities: "Distinct Activities", participations: "Role Associations", role_attendee: "Attendee", role_resource_person: "Resource Person", role_coordinator: "Coordinator", type_fdp: "FDP", type_workshop: "Workshop", type_sttp: "STTP" }} rows={dashboard.faculty_performance} loading={dashboardLoading} note="Distinct activity totals do not increase when the same Faculty member holds multiple roles in one activity." onSelect={(row, key) => viewFacultyPerformance(row.id, key)} />

      {showFacultyParticipants && (
        <section className="panel" id="faculty-participants">
          <div className="row-between">
            <h2>Faculty participation · {dashboard.faculty_participants.length}</h2>
            <button className="secondary small" onClick={() => { setShowFacultyParticipants(false); setActiveMetric(""); }}>Close</button>
          </div>
          <p className="muted">One row per Faculty Master record. Activity count is distinct across the current dashboard filters; speaker-only associations do not contribute.</p>
          {!dashboard.faculty_participants.length ? <p className="dash-empty">No Faculty participants match the current filters.</p> : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Faculty</th><th>Activity participation</th><th>Records</th></tr></thead>
                <tbody>
                  {dashboard.faculty_participants.map((person) => (
                    <tr key={person.id}>
                      <td>{person.name}{person.is_active ? "" : " (historical)"}</td>
                      <td>{person.activity_count}</td>
                      <td><button className="link-button" onClick={() => viewFacultyActivities(person.id)}>View matching activities</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      <section className="panel">
        <h2>Find activities</h2>
        <div className="filters">
          <label className="field">
            Search
            <input value={search} placeholder="Title, organizer, or Faculty" onChange={(event) => resetPage(() => setSearch(event.target.value))} />
          </label>
          <label className="field">
            Activity type
            <select value={activityType} onChange={(event) => resetPage(() => { setActivityType(event.target.value); setActivityGroup(""); })}>
              <option value="">All types</option>
              {types.map((value) => <option key={value} value={value}>{activityTypeLabels[value]}</option>)}
            </select>
          </label>
          <label className="field">
            Faculty
            <select value={facultyId} onChange={(event) => resetPage(() => setFacultyId(event.target.value))}>
              <option value="">All Faculty</option>
              {masters?.faculty.map((person) => <option key={person.id} value={person.id}>{person.name}{person.is_active ? "" : " (historical)"}</option>)}
            </select>
          </label>
          <label className="field">
            Role
            <select value={role} onChange={(event) => resetPage(() => setRole(event.target.value))}>
              <option value="">All roles</option>
              {roles.map((value) => <option key={value} value={value}>{label(value)}</option>)}
            </select>
          </label>
          <label className="field">
            Record status
            <span className="check"><input type="checkbox" checked={includeInactive} onChange={(event) => resetPage(() => setIncludeInactive(event.target.checked))} />Include inactive</span>
          </label>
          <div className="actions"><button type="button" className="secondary" onClick={resetFilters}>Reset filters</button></div>
        </div>
      </section>

      <section className="panel" id="fdp-records">
        <div className="row-between">
          <h2>{activeMetric ? kpiLabels[activeMetric] : "Activities"} · {result.total}</h2>
          {activeMetric && <button className="secondary small" onClick={() => selectMetric("")}>Clear KPI selection</button>}
        </div>
        {loading ? <p role="status">Loading activities…</p> : !result.items.length ? <p className="dash-empty">No activities match the current filters.</p> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Activity</th><th>Organizer</th><th>Dates</th><th>Faculty</th><th>Status</th><th>Actions</th></tr></thead>
              <tbody>
                {result.items.map((activity) => (
                  <tr key={activity.id}>
                    <td><strong>{activity.title}</strong><small>{activityTypeLabels[activity.activity_type] || label(activity.activity_type)}</small></td>
                    <td>{activity.organizing_institution}</td>
                    <td>{activity.start_date}{activity.end_date && " – " + activity.end_date}</td>
                    <td>{activity.participants.length}</td>
                    <td>{activity.is_active ? "Active" : "Inactive"}</td>
                    <td className="actions">
                      <Link href={"/fdp/" + activity.id}>View</Link>
                      <Link href={"/fdp/" + activity.id + "/edit"}>Edit</Link>
                      {activity.is_active && <button className="danger small" onClick={() => deactivate(activity.id)}>Deactivate</button>}
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
