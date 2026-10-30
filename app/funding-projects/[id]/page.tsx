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
function normalizedRoleLabel(role: string) {
  if (role === "LEAD_PI") return "Lead PI / Principal Investigator";
  if (role === "MEMBER_PI") return "Member PI";
  if (role === "CO_PI") return "Co-PI / Co-Investigator";
  if (role === "ADMIN_PI") return "Admin PI";
  if (role === "PI") return "Historical Principal Investigator";
  if (role === "CO_INVESTIGATOR") return "Historical Co-Investigator";
  return label(role);
}

function financialDetails(record: FundingProject) {
  if (record.category === "SPONSORED_RESEARCH") {
    return [["Proposed / requested amount", amount(record.proposed_amount)], ["Sanctioned amount", amount(record.sanctioned_amount)]];
  }
  if (record.category === "CONSULTANCY") {
    return [["Consultancy contract / approved amount", amount(record.contract_amount)], ["Amount received", amount(record.amount_received)]];
  }
  return [["Amount sanctioned", amount(record.sanctioned_amount)], ["Amount utilized", amount(record.amount_utilized)]];
}

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
  const roleOrder = ["LEAD_PI", "MEMBER_PI", "CO_PI", "ADMIN_PI", "BENEFICIARY", "PI", "CO_INVESTIGATOR"];
  const investigators = (members: typeof record.faculty) => members.length ? <ul>{members.map((member) => <li key={member.id || `${member.role}-${member.faculty_name}`}><strong>{member.faculty_name || member.investigator_name}</strong>{` · ${member.agency_role_label || normalizedRoleLabel(member.role)}`}{member.is_designated_lead && " · Designated overall lead"}{member.department_name && ` · ${member.department_name}`}{member.institution_name && ` · ${member.institution_name}`}{member.affiliation_type === "FACULTY_MASTER" && " · Faculty Master"}</li>)}</ul> : "—";
  return <><Link href={back}>← Back to funding records</Link><div className="page-heading"><div><div className="eyebrow">{label(record.category)} · {record.is_active ? "Active" : "Inactive"}</div><h1>{record.title}</h1><p>{record.department}{record.funding_agency && ` · ${record.funding_agency}`}</p></div><div className="actions">{record.is_active ? <><Link className="button" href={`/funding-projects/${id}/edit`}>Edit record</Link><button className="secondary" disabled={busy} onClick={deactivate}>Deactivate</button></> : <button disabled={busy} onClick={reactivate}>Reactivate</button>}</div></div>{error && <div className="error">{error}</div>}
    <section className="panel"><h2>Project and financial details</h2><dl className="detail-grid">{[["Status", label(record.status)], ["Reference / sanction number", record.reference_number], ["Proposal submitted", record.proposal_submission_date], ["Sanction date", record.sanction_date], ["Start date", record.start_date], ["End date", record.end_date], ...financialDetails(record)].map(([key, value]) => <div key={String(key)}><dt>{key}</dt><dd>{value || "—"}</dd></div>)}</dl>{record.category === "SPONSORED_RESEARCH" && !["SANCTIONED", "ONGOING", "COMPLETED"].includes(record.status) && record.sanctioned_amount !== null && record.sanctioned_amount !== undefined && <p className="muted">A historical amount remains in the sanctioned-amount field for this pre-sanction record. It is excluded from award totals until its meaning is confirmed.</p>}{record.description && <p>{record.description}</p>}{record.deliverables && <p><strong>Deliverables:</strong> {record.deliverables}</p>}{record.outcomes && <p><strong>Outcomes:</strong> {record.outcomes}</p>}{record.completion_details && <p><strong>Completion details:</strong> {record.completion_details}</p>}</section>
    <section className="panel"><h2>Investigators and beneficiaries</h2>{roleOrder.map((role) => { const members = record.faculty.filter((member) => member.role === role); return members.length ? <div key={role}><strong>{normalizedRoleLabel(role)}</strong>{investigators(members)}</div> : null; })}</section>
    <EvidenceManager entity="funding-projects" id={Number(id)} categories={evidenceTypes} />
  </>;
}
