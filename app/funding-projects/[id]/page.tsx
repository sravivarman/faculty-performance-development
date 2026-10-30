"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import EvidenceManager from "@/components/EvidenceManager";
import { FundingProject } from "@/components/FundingEditor";
import { api, label } from "@/lib/api";

const evidenceTypes = ["PROPOSAL", "SANCTION_LETTER", "AGREEMENT", "FUNDING_RECEIPT", "UTILIZATION_CERTIFICATE", "PROGRESS_REPORT", "COMPLETION_REPORT", "OUTCOME_EVIDENCE", "OTHER"];

function backPath(category: string) { return category === "CONSULTANCY" ? "/consultancy" : category === "INTERNAL_GRANT" ? "/seed-money" : "/research-projects"; }
function amount(value: string | number | null | undefined) { return value === null || value === undefined ? "—" : new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(Number(value)); }

export default function FundingProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [record, setRecord] = useState<(FundingProject & { is_active: boolean })>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => api<FundingProject & { is_active: boolean }>(`/funding-projects/${id}`).then(setRecord).catch((reason: Error) => setError(reason.message));
  useEffect(() => { void load(); }, [id]);
  async function deactivate() { if (!confirm("Deactivate this funding record? Its Faculty associations and evidence remain available.")) return; setBusy(true); try { await api(`/funding-projects/${id}`, { method: "DELETE" }); load(); } catch (reason) { setError((reason as Error).message); } finally { setBusy(false); } }
  async function reactivate() { setBusy(true); try { await api(`/funding-projects/${id}/reactivate`, { method: "POST" }); load(); } catch (reason) { setError((reason as Error).message); } finally { setBusy(false); } }
  if (error && !record) return <div className="error">{error}</div>;
  if (!record) return <p role="status">Loading funding record…</p>;
  const back = backPath(record.category);
  const pi = record.faculty.filter((member) => member.role === "PI");
  const coPi = record.faculty.filter((member) => member.role === "CO_PI");
  const beneficiaries = record.faculty.filter((member) => member.role === "BENEFICIARY");
  return <><Link href={back}>← Back to funding records</Link><div className="page-heading"><div><div className="eyebrow">{label(record.category)} · {record.is_active ? "Active" : "Inactive"}</div><h1>{record.title}</h1><p>{record.department}{record.funding_agency && ` · ${record.funding_agency}`}</p></div><div className="actions">{record.is_active ? <><Link className="button" href={`/funding-projects/${id}/edit`}>Edit record</Link><button className="secondary" disabled={busy} onClick={deactivate}>Deactivate</button></> : <button disabled={busy} onClick={reactivate}>Reactivate</button>}</div></div>{error && <div className="error">{error}</div>}
    <section className="panel"><h2>Project and financial details</h2><dl className="detail-grid">{[["Status", label(record.status)], ["Reference / sanction number", record.reference_number], ["Proposal submitted", record.proposal_submission_date], ["Sanction date", record.sanction_date], ["Start date", record.start_date], ["End date", record.end_date], ["Sanctioned amount", amount(record.sanctioned_amount)], ["Amount received", amount(record.amount_received)], ["Amount utilized", amount(record.amount_utilized)]].map(([key, value]) => <div key={String(key)}><dt>{key}</dt><dd>{value || "—"}</dd></div>)}</dl>{record.description && <p>{record.description}</p>}{record.deliverables && <p><strong>Deliverables:</strong> {record.deliverables}</p>}{record.outcomes && <p><strong>Outcomes:</strong> {record.outcomes}</p>}{record.completion_details && <p><strong>Completion details:</strong> {record.completion_details}</p>}</section>
    <section className="panel"><h2>Faculty association</h2><p><strong>Principal Investigator:</strong> {pi.map((member) => member.faculty_name).join(", ") || "—"}</p><p><strong>Co-Principal Investigators:</strong> {coPi.map((member) => member.faculty_name).join(", ") || "—"}</p>{beneficiaries.length > 0 && <p><strong>Internal grant beneficiaries:</strong> {beneficiaries.map((member) => member.faculty_name).join(", ")}</p>}</section>
    <EvidenceManager entity="funding-projects" id={Number(id)} categories={evidenceTypes} />
  </>;
}
