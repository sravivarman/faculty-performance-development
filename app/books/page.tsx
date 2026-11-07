"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import DateRangeFilter, { useDateRange } from "@/components/DateRange";
import { DashboardError, DashboardFilters, DashboardFrame, KpiGrid as KpiCards, ResearchPageHeader } from "@/components/dashboard/UI";
import { Distribution, SeriesChart } from "@/components/dashboard/Charts";
import FacultyContributionTable from "@/components/dashboard/FacultyContributionTable";
import PaginationControls, { RecordPageSize } from "@/components/PaginationControls";
import type { TrendPoint } from "@/lib/dashboard-charts";
import BookTable from "@/components/BookTable";
import { api, label, Masters, paginatedResult } from "@/lib/api";
import { Book, bookMetrics, BookPersonKpi } from "@/lib/books";

type PageResult = { items: Book[]; total: number; page: number; page_size: number | "all" };
const FILTER_KEYS = ["department_id", "attribution_mode", "work_type", "faculty_id", "student_participation", "interdepartmental", "external_collaboration", "publisher", "isbn_search", "include_inactive"];
const pageSizeFrom = (value: string | null): RecordPageSize => value === "all" ? "all" : [10, 25, 50].includes(Number(value)) ? Number(value) as 10 | 25 | 50 : 25;

export default function BooksDashboard() {
  const { range, ready } = useDateRange();
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [drill, setDrill] = useState<Record<string, string>>({ metric: "total" });
  const [masters, setMasters] = useState<Masters>();
  const [options, setOptions] = useState<{ publishers: string[]; current_department: string }>();
  const [classification, setClassification] = useState<Record<string, number>>({});
  const [counts, setCounts] = useState<Record<string, number | null>>({});
  const [result, setResult] = useState<PageResult>({ items: [], total: 0, page: 1, page_size: 25 });
  const [faculty, setFaculty] = useState<BookPersonKpi[]>([]);
  const [students, setStudents] = useState<BookPersonKpi[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [initialized, setInitialized] = useState(false);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [chartError, setChartError] = useState("");
  const [listLoading, setListLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<RecordPageSize>(25);
  const previousRange = useRef("");

  useEffect(() => {
    Promise.all([api<Masters>("/masters"), api<{ publishers: string[]; current_department: string }>("/book-options")])
      .then(([masterData, optionData]) => { setMasters(masterData); setOptions(optionData); })
      .catch((reason) => setError(reason.message));
    const params = new URLSearchParams(window.location.search);
    setFilters(Object.fromEntries(FILTER_KEYS.map((key) => [key, params.get(key) || ""])));
    setDrill({ metric: params.get("metric") || "total", drill_faculty_id: params.get("drill_faculty_id") || "", drill_student_id: params.get("drill_student_id") || "", list_from_date: params.get("list_from_date") || "", list_to_date: params.get("list_to_date") || "" });
    setPage(Math.max(1, Number(params.get("page")) || 1));
    setPageSize(pageSizeFrom(params.get("page_size")));
    setInitialized(true);
  }, []);

  const dashboardQuery = new URLSearchParams(Object.entries({ ...filters, ...range }).filter(([, value]) => value)).toString();
  const listQuery = new URLSearchParams(Object.entries({ ...filters, ...range, ...drill, page: String(page), page_size: String(pageSize), ...(drill.list_from_date ? { from_date: drill.list_from_date, to_date: drill.list_to_date } : {}) }).filter(([key, value]) => value && !key.startsWith("list_"))).toString();
  const reportQuery = new URLSearchParams(Object.entries({ ...filters, ...range, ...drill, page: String(page), page_size: String(pageSize) }).filter(([, value]) => value)).toString();

  useEffect(() => {
    if (!ready || !initialized) return;
    let active = true;
    setLoading(true); setChartError("");
    api<{ totals: Record<string, number | null>; faculty: BookPersonKpi[]; trend: TrendPoint[]; classification: Record<string, number> }>(`/book-dashboard?${dashboardQuery}`)
      .then((data) => { if (active) { setCounts(data.totals); setClassification(data.classification); setFaculty(data.faculty); setTrend(data.trend); } })
      .catch((reason) => { if (active) { setCounts({}); setFaculty([]); setTrend([]); setChartError(reason.message); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [dashboardQuery, ready, initialized]);

  useEffect(() => {
    if (!ready || !initialized) return;
    let active = true;
    setListLoading(true); setError("");
    api<unknown>(`/books?${listQuery}`)
      .then((data) => { if (active) setResult(paginatedResult<Book>(data, "Books / Chapters")); })
      .catch((reason) => { if (active) setError(reason.message); })
      .finally(() => { if (active) setListLoading(false); });
    return () => { active = false; };
  }, [listQuery, ready, initialized]);

  useEffect(() => {
    if (!ready || !initialized) return;
    let active = true;
    api<BookPersonKpi[]>(`/book-kpis/students?${dashboardQuery}`).then((data) => { if (active) setStudents(data); }).catch((reason) => { if (active) setError(reason.message); });
    return () => { active = false; };
  }, [dashboardQuery, ready, initialized]);

  useEffect(() => {
    if (ready && initialized && window.location.pathname === "/books") window.history.replaceState(window.history.state, "", `/books?${reportQuery}`);
  }, [reportQuery, ready, initialized]);

  useEffect(() => {
    if (!ready) return;
    const key = `${range.from_date}/${range.to_date}`;
    if (previousRange.current && previousRange.current !== key) { setDrill((current) => ({ ...current, list_from_date: "", list_to_date: "" })); setPage(1); }
    previousRange.current = key;
  }, [range, ready]);

  function filter(key: string, value: string) { setFilters((current) => ({ ...current, [key]: value })); setDrill({ metric: "total" }); setPage(1); }
  function resetFilters() { setFilters({}); setDrill({ metric: "total" }); setPage(1); }
  function select(values: Record<string, string>) { setDrill(values); setPage(1); document.getElementById("book-records")?.scrollIntoView({ behavior: "smooth" }); }

  function peopleTable(rows: BookPersonKpi[], kind: "faculty" | "student") {
    const keys = kind === "faculty" ? ["books_claimed", "books_authored", "chapters_claimed", "chapters_authored", "claimed", "authored"] : ["books_authored", "chapters_authored", "authored"];
    return <div className="table-wrap"><table><thead><tr><th>{kind === "faculty" ? "Faculty" : "Student / Roll number"}</th>{keys.map((key) => <th key={key}>{key === "authored" ? (kind === "faculty" ? "Total Authored" : "Total Works") : key === "claimed" ? "Total Claimed" : label(key)}</th>)}{kind === "student" && <th>Faculty Collaborators</th>}</tr></thead><tbody>{rows.map((person) => <tr key={person.id}><td>{person.name}<small>{person.roll_number}</small></td>{keys.map((key) => <td key={key}><button className="link-button" onClick={() => select({ [kind === "faculty" ? "drill_faculty_id" : "drill_student_id"]: String(person.id), metric: key })}>{person[key as keyof BookPersonKpi] as number}</button></td>)}{kind === "student" && <td>{person.faculty_collaborators?.map((member) => member.name).join(", ") || "—"}</td>}</tr>)}</tbody></table></div>;
  }

  return <DashboardFrame>
    <ResearchPageHeader title="Books / Chapters Overview" subtitle="One work, one Department count. Every author, editor and collaboration retained."><Link href="/books/records">All work records</Link><Link className="button" href="/books/new">+ Add Book / Book Chapter</Link></ResearchPageHeader>
    <DateRangeFilter />
    {error && <div className="error" role="alert">{error}</div>}
    <DashboardFilters>
      <label className="field">Department<select value={filters.department_id || ""} onChange={(event) => filter("department_id", event.target.value)}><option value="">All Departments</option>{masters?.departments.map((department) => <option key={department.id} value={department.id}>{department.name} ({department.code}){department.is_active ? "" : " (historical)"}</option>)}</select></label>
      {filters.department_id && <label className="field">Department Attribution<select value={filters.attribution_mode || "CURRENT"} onChange={(event) => filter("attribution_mode", event.target.value)}><option value="CURRENT">Current Department</option><option value="AT_ACTIVITY_DATE">Activity-Date Department</option></select></label>}
      <label className="field">Work Type<select value={filters.work_type || ""} onChange={(event) => filter("work_type", event.target.value)}><option value="">Books + Chapters</option><option value="BOOK">Book</option><option value="BOOK_CHAPTER">Book Chapter</option></select></label>
      <label className="field">Faculty Contributor<select value={filters.faculty_id || ""} onChange={(event) => filter("faculty_id", event.target.value)}><option value="">All Faculty</option>{masters?.faculty.map((person) => <option key={person.id} value={person.id}>{person.name}{person.is_active ? "" : " (historical)"}</option>)}</select></label>
      <label className="field">Student Participation<select value={filters.student_participation || ""} onChange={(event) => filter("student_participation", event.target.value)}><option value="">All Works</option><option value="true">With Student Contributors</option><option value="false">Without Student Contributors</option></select></label>
      <label className="field">Cross-Department Collaboration<select value={filters.interdepartmental || ""} onChange={(event) => filter("interdepartmental", event.target.value)}><option value="">All Works</option><option value="true">With Cross-Department Collaboration</option><option value="false">Without Cross-Department Collaboration</option></select></label>
      <label className="field">External Collaboration<select value={filters.external_collaboration || ""} onChange={(event) => filter("external_collaboration", event.target.value)}><option value="">All Works</option><option value="true">With External Collaboration</option><option value="false">Without External Collaboration</option></select></label>
      <label className="field">Publisher<select value={filters.publisher || ""} onChange={(event) => filter("publisher", event.target.value)}><option value="">All publishers</option>{options?.publishers.map((publisher) => <option key={publisher}>{publisher}</option>)}</select></label>
      <label className="field">ISBN search<input value={filters.isbn_search || ""} onChange={(event) => filter("isbn_search", event.target.value)} /></label>
      <label className="check"><input type="checkbox" checked={filters.include_inactive === "true"} onChange={(event) => filter("include_inactive", event.target.checked ? "true" : "")} />Include inactive records</label>
      <button type="button" className="secondary" onClick={resetFilters}>Reset filters</button>
    </DashboardFilters>
    {filters.department_id && filters.attribution_mode === "AT_ACTIVITY_DATE" && <p className="muted compact-note">Only contributors with verified primary Department affiliations on the publication date are included. Unverified historical baseline affiliations are excluded.</p>}
    <KpiCards labels={{ total: "Total Works", books: "Books", chapters: "Book Chapters", international: "International", national: "National", with_students: "Student-involved", faculty_contributors: "Faculty Contributors" }} counts={counts} loading={loading} active={drill.metric} onSelect={(metric) => select({ metric })} />
    <p className="muted">Publication date is used for every count, with both boundaries included. Chapters require an eligible chapter author; parent-book editors alone do not qualify. Author counts exclude editors.</p>
    <details className="dash-additional"><summary>Collaboration and authorship indicators</summary><KpiCards labels={{ interdepartmental: "Cross-Department Collaboration", external_collaboration: bookMetrics.external_collaboration, unique_faculty: bookMetrics.unique_faculty, unique_students: bookMetrics.unique_students }} counts={counts} loading={loading} onSelect={(metric) => select({ metric })} /></details>
    <DashboardError message={chartError} />
    <div className="dash-charts"><Distribution title="Books vs Chapters" labels={{ books: "Books", chapters: "Book Chapters" }} counts={{ books: counts.books || 0, chapters: counts.chapters || 0 }} onSelect={(metric) => select({ metric })} loading={loading} error={chartError} /><SeriesChart title="Books / Chapters Trend" rows={trend} series={{ books: "Books", chapters: "Book Chapters" }} loading={loading} error={chartError} onSelect={(row, key) => select({ metric: key, list_from_date: String(row.from_date), list_to_date: String(row.to_date) })} /><Distribution title="Recorded historical classifications" labels={{ international: "International", national: "National", other: "Other", unknown: "Unknown" }} counts={classification} loading={loading} error={chartError} onSelect={(metric) => select({ metric })} note="These retained legacy values are not measures of publisher quality, indexing, or collaboration." /></div>
    <section className="panel" id="book-records"><div className="row-between"><h2>{bookMetrics[drill.metric as keyof typeof bookMetrics] || label(drill.metric)} · {loading ? "Loading…" : `${result.total} records`}</h2><button className="secondary small" onClick={() => { setDrill({ metric: "total" }); setPage(1); }}>Reset drill-down</button></div>{["unique_faculty", "unique_students", "faculty_contributors"].includes(drill.metric) && <p className="muted">The KPI counts distinct authors; this list shows the works involving those authors.</p>}<p className="dash-footnote">{drill.list_from_date || range.from_date} to {drill.list_to_date || range.to_date}</p>{listLoading ? <p role="status">Loading book records...</p> : <BookTable books={result.items} query={reportQuery} />}<PaginationControls page={result.page} pageSize={pageSize} total={result.total} loading={listLoading} onPageChange={setPage} onPageSizeChange={(next) => { setPageSize(next); setPage(1); }} /></section>
    <FacultyContributionTable title="Faculty contributions" columns={{ books_claimed: "Books Claimed", books_authored: "Books Authored", chapters_claimed: "Chapters Claimed", chapters_authored: "Chapters Authored", claimed: "Total Claimed", authored: "Total Authored", participated: "Total Works" }} rows={faculty.map(({ id, name, books_claimed, books_authored, chapters_claimed, chapters_authored, claimed, authored, participated }) => ({ id, name, books_claimed, books_authored, chapters_claimed, chapters_authored, claimed, authored, participated }))} loading={loading} error={chartError} note="Claims and authored works remain separate; eligible editors appear in the faculty profile." onSelect={(row, key) => select({ drill_faculty_id: String(row.id), metric: key })} />
    <section className="panel"><h2>Student authorship</h2>{peopleTable(students, "student")}</section>
  </DashboardFrame>;
}
