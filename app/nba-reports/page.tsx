"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, label, Year } from "@/lib/api";

type DateBasis = { value: string; field: string; label: string };
type ReportOption = { category: string; table: string; default_date_basis: string; default_date_basis_label: string };
type Options = { academic_years: Year[]; reports: ReportOption[]; date_bases: DateBasis[]; default_eligible_statuses: string[] };
type FundingRecord = { id: number; title: string; status: string; sanction_date?: string | null; proposal_submission_date?: string | null; start_date?: string | null; funding_agency?: string | null };
type Preview = {
  table: string;
  policy: { date_basis: string; date_field: string; date_basis_label: string; eligible_statuses: string[]; include_inactive: boolean; note: string };
  periods: { code: string; academic_year: Year; count: number; records: FundingRecord[] }[];
  incomplete_records: { id: number; title: string; status: string; missing_label: string; eligible_for_selected_policy: boolean }[];
  outside_selected_relative_years: number;
};

export default function NbaReportsPage() {
  const [options, setOptions] = useState<Options>();
  const [category, setCategory] = useState("SPONSORED_RESEARCH");
  const [yearId, setYearId] = useState("");
  const [dateBasis, setDateBasis] = useState("");
  const [relativeYearCount, setRelativeYearCount] = useState("3");
  const [preview, setPreview] = useState<Preview>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api<Options>("/nba/funding-reporting-options")
      .then((data) => {
        setOptions(data);
        setYearId(String(data.academic_years[0]?.id || ""));
        setDateBasis(data.reports.find((report) => report.category === category)?.default_date_basis || "SANCTION_DATE");
      })
      .catch((reason: Error) => setError(reason.message));
  }, []);

  function changeCategory(next: string) {
    setCategory(next);
    setDateBasis(options?.reports.find((report) => report.category === next)?.default_date_basis || "SANCTION_DATE");
    setPreview(undefined);
  }

  async function loadPreview() {
    if (!yearId) return;
    setLoading(true);
    setError("");
    try {
      const query = new URLSearchParams({ reference_academic_year_id: yearId, relative_year_count: relativeYearCount, date_basis: dateBasis });
      setPreview(await api<Preview>(`/nba/funding-reports/${category}?${query}`));
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return <>
    <div className="page-heading"><div><div className="eyebrow">NBA reporting preparation</div><h1>Funding-report year selection</h1><p>Select an existing Academic Year Master record. This preview does not create academic years or export files.</p></div><Link className="secondary button" href="/masters">Manage Academic Years</Link></div>
    {error && <div className="error" role="alert">{error}</div>}
    <section className="panel"><h2>Report scope</h2><p className="muted">The default date basis is visible and can be changed before export. The default eligibility policy includes active sanctioned, ongoing, and completed records only.</p><div className="filters">
      <label className="field">NBA report<select value={category} onChange={(event) => changeCategory(event.target.value)}>{options?.reports.map((report) => <option key={report.category} value={report.category}>{report.table}</option>)}</select></label>
      <label className="field">Reference Academic Year<select value={yearId} onChange={(event) => { setYearId(event.target.value); setPreview(undefined); }} disabled={!options?.academic_years.length}><option value="">Select Academic Year</option>{options?.academic_years.map((year) => <option key={year.id} value={year.id}>{year.name} · {year.start_date} to {year.end_date}</option>)}</select></label>
      <label className="field">Reporting date basis<select value={dateBasis} onChange={(event) => { setDateBasis(event.target.value); setPreview(undefined); }}>{options?.date_bases.map((basis) => <option key={basis.value} value={basis.value}>{basis.label}</option>)}</select></label>
      <label className="field">Relative Academic Years<select value={relativeYearCount} onChange={(event) => { setRelativeYearCount(event.target.value); setPreview(undefined); }}><option value="3">CAY through CAYm2</option><option value="4">CAY through CAYm3</option><option value="5">CAY through CAYm4</option></select></label>
      <div className="actions"><button type="button" disabled={!yearId || loading} onClick={loadPreview}>{loading ? "Loading…" : "Preview report records"}</button></div>
    </div></section>
    {preview && <>
      <section className="panel"><h2>{preview.table}</h2><p className="muted">{preview.policy.date_basis_label} is used for this preview. Eligible statuses: {preview.policy.eligible_statuses.map(label).join(", ")}. {preview.policy.note}</p></section>
      {preview.periods.map((period) => <section className="panel" key={period.code}><div className="row-between"><h2>{period.code} · {period.academic_year.name}</h2><strong>{period.count} records</strong></div><p className="muted">{period.academic_year.start_date} to {period.academic_year.end_date}</p>{period.records.length ? <div className="table-wrap"><table><thead><tr><th>Project</th><th>Agency / client</th><th>Status</th><th>{preview.policy.date_basis_label}</th><th>Details</th></tr></thead><tbody>{period.records.map((record) => <tr key={record.id}><td>{record.title}</td><td>{record.funding_agency || "—"}</td><td>{label(record.status)}</td><td>{String(record[preview.policy.date_field as keyof FundingRecord] || "—")}</td><td><Link href={`/funding-projects/${record.id}`}>View</Link></td></tr>)}</tbody></table></div> : <p className="dash-empty">No eligible records fall within this Academic Year.</p>}</section>)}
      <section className="panel"><h2>Records requiring review · {preview.incomplete_records.length}</h2><p className="muted">Records without the selected reporting date are not assigned to any Academic Year.</p>{preview.incomplete_records.length ? <div className="table-wrap"><table><thead><tr><th>Project</th><th>Status</th><th>Missing field</th><th>Eligibility</th><th>Details</th></tr></thead><tbody>{preview.incomplete_records.map((record) => <tr key={record.id}><td>{record.title}</td><td>{label(record.status)}</td><td>{record.missing_label}</td><td>{record.eligible_for_selected_policy ? "Eligible once dated" : "Not eligible under current status policy"}</td><td><Link href={`/funding-projects/${record.id}`}>Review record</Link></td></tr>)}</tbody></table></div> : <p className="dash-empty">No selected records are missing the reporting date.</p>}{preview.outside_selected_relative_years > 0 && <p className="muted">{preview.outside_selected_relative_years} eligible records fall outside the selected relative-year window.</p>}</section>
    </>}
  </>;
}
