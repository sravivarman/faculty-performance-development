"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
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
    <ResearchPageHeader title="Research Overview" subtitle="Department research performance and activity"><Link className="button" href="/publications/new">+ Add publication</Link></ResearchPageHeader>
    <DateRangeFilter />
    <section className="panel"><label className="field">Academic Year Master<select aria-label="Academic Year Master" value={selectedAcademicYear?.id ?? ""} onChange={(event) => {
      const year = masters?.academic_years.find((item) => item.id === Number(event.target.value));
      if (year) setRange({ from_date: year.start_date, to_date: year.end_date }, "Custom");
    }}><option value="">Custom date range</option>{masters?.academic_years.map((year) => <option key={year.id} value={year.id}>{year.name} · {year.start_date} to {year.end_date}</option>)}</select></label>
      <p className="muted">Selecting a configured Academic Year applies its stored inclusive dates. Custom From/To dates remain available above.</p></section>
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
