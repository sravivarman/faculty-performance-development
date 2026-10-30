"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import FacultySelector from "@/components/FacultySelector";
import { api, label, Masters } from "@/lib/api";

export const fundingCategories = ["SPONSORED_RESEARCH", "CONSULTANCY", "INTERNAL_GRANT"] as const;
export const fundingStatuses = ["DRAFT", "SUBMITTED", "UNDER_REVIEW", "SANCTIONED", "ONGOING", "COMPLETED", "REJECTED", "WITHDRAWN"] as const;
const facultyRoles = ["LEAD_PI", "MEMBER_PI", "CO_PI", "ADMIN_PI", "BENEFICIARY"] as const;
const piLevelRoles = new Set(["LEAD_PI", "MEMBER_PI"]);
const roleLabels: Record<string, string> = {
  LEAD_PI: "Lead PI / Principal Investigator",
  MEMBER_PI: "Member PI",
  CO_PI: "Co-PI / Co-Investigator",
  ADMIN_PI: "Admin PI",
  BENEFICIARY: "Beneficiary",
};
const legacyRoleLabels: Record<string, string> = {
  PI: "Historical Principal Investigator",
  CO_INVESTIGATOR: "Historical Co-Investigator",
};

export type FundingFaculty = {
  id?: number;
  faculty_id: number | null;
  role: string;
  faculty_name?: string | null;
  investigator_name?: string | null;
  department_name?: string | null;
  institution_name?: string | null;
  affiliation_type?: "FACULTY_MASTER" | "MANUAL";
  display_order?: number;
  agency_role_label?: string | null;
  is_designated_lead?: boolean;
};
export type FundingProject = {
  id?: number;
  title: string;
  category: string;
  department: string;
  funding_agency?: string | null;
  proposal_submission_date?: string | null;
  sanction_date?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  proposed_amount?: string | number | null;
  sanctioned_amount?: string | number | null;
  contract_amount?: string | number | null;
  amount_received?: string | number | null;
  amount_utilized?: string | number | null;
  reference_number?: string | null;
  status: string;
  description?: string | null;
  outcomes?: string | null;
  deliverables?: string | null;
  completion_details?: string | null;
  internal_notes?: string | null;
  source_url?: string | null;
  faculty: FundingFaculty[];
};

type Props = { category: (typeof fundingCategories)[number]; initial?: FundingProject };

function emptyProject(category: Props["category"]): FundingProject {
  return { title: "", category, department: "", funding_agency: null, proposal_submission_date: null, sanction_date: null, start_date: null, end_date: null, proposed_amount: null, sanctioned_amount: null, contract_amount: null, amount_received: null, amount_utilized: null, reference_number: null, status: "DRAFT", description: null, outcomes: null, deliverables: null, completion_details: null, internal_notes: null, source_url: null, faculty: [] };
}

function asInput(value: string | number | null | undefined) {
  return value === null || value === undefined ? "" : String(value);
}

export default function FundingEditor({ category, initial }: Props) {
  const router = useRouter();
  const [draft, setDraft] = useState<FundingProject>(initial || emptyProject(category));
  const [masters, setMasters] = useState<Masters>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => setDraft(initial ? { ...initial, category } : emptyProject(category)), [category, initial]);
  useEffect(() => { api<Masters>("/masters").then(setMasters).catch((reason: Error) => setError(reason.message)); }, []);

  function changeFaculty(index: number, key: keyof FundingFaculty, value: string | number | boolean | null) {
    const faculty = draft.faculty.map((member, current) => current === index
      ? { ...member, [key]: key === "faculty_id" ? value ? Number(value) : null : value, ...(key === "role" ? { is_designated_lead: value === "LEAD_PI" } : {}) }
      : member);
    const current = faculty[index];
    if (current.faculty_id && faculty.filter((member) => member.faculty_id === current.faculty_id && member.role === current.role).length > 1) {
      setError("Duplicate Faculty-role associations are not allowed.");
      return;
    }
    setError("");
    setDraft({ ...draft, faculty });
  }

  function changeInvestigatorMode(index: number, mode: "FACULTY_MASTER" | "MANUAL") {
    setError("");
    setDraft({ ...draft, faculty: draft.faculty.map((member, current) => current !== index ? member : mode === "MANUAL"
      ? { ...member, affiliation_type: "MANUAL", faculty_id: null, investigator_name: "", department_name: "", institution_name: "" }
      : { ...member, affiliation_type: "FACULTY_MASTER", faculty_id: null, investigator_name: null, department_name: null, institution_name: null }) });
  }

  function moveInvestigator(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= draft.faculty.length) return;
    const faculty = [...draft.faculty];
    [faculty[index], faculty[target]] = [faculty[target], faculty[index]];
    setDraft({ ...draft, faculty });
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (draft.faculty.some((member) => !member.faculty_id && !(member.investigator_name || "").trim())) {
      setError("Select a Faculty Master investigator or enter a name for every project association.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const { id, ...payload } = draft;
      const saved = id
        ? await api<FundingProject>(`/funding-projects/${id}`, { method: "PUT", body: JSON.stringify(payload) })
        : await api<FundingProject>("/funding-projects", { method: "POST", body: JSON.stringify(payload) });
      router.push(`/funding-projects/${saved.id}`);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const categoryText = category === "SPONSORED_RESEARCH" ? "Sponsored research project" : category === "CONSULTANCY" ? "Consultancy project" : "Seed money / internal grant";
  const manualInvestigatorsAllowed = category !== "INTERNAL_GRANT";
  const setText = (key: keyof FundingProject, value: string) => setDraft({ ...draft, [key]: value || null });
  const financialFields = category === "SPONSORED_RESEARCH"
    ? [["Proposed / requested amount (INR)", "proposed_amount"], ["Sanctioned amount (INR)", "sanctioned_amount"]]
    : category === "CONSULTANCY"
      ? [["Consultancy contract / approved amount (INR)", "contract_amount"], ["Amount received (INR)", "amount_received"]]
      : [["Amount sanctioned (INR)", "sanctioned_amount"], ["Amount utilized (INR)", "amount_utilized"]];
  const historicalPreSanctionAmount = category === "SPONSORED_RESEARCH"
    && !["SANCTIONED", "ONGOING", "COMPLETED"].includes(draft.status)
    && draft.sanctioned_amount !== null && draft.sanctioned_amount !== undefined;

  return <form className="fdp-editor" onSubmit={save}>
    {error && <div className="error" role="alert">{error}</div>}
    <section className="panel">
      <h2>Project details</h2>
      <p className="muted">{categoryText}. Amounts are recorded in INR; reporting derives lakhs without changing the stored amount.</p>
      <div className="split">
        <label className="field wide">Project title *<input required value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></label>
        <label className="field">Department where sanctioned *<input required value={draft.department} onChange={(event) => setDraft({ ...draft, department: event.target.value })} /></label>
        <label className="field">Project status *<select value={draft.status} onChange={(event) => setDraft({ ...draft, status: event.target.value })}>{fundingStatuses.map((status) => <option key={status} value={status}>{label(status)}</option>)}</select></label>
        <label className="field">Funding agency / organization<input value={draft.funding_agency || ""} onChange={(event) => setText("funding_agency", event.target.value)} /></label>
        <label className="field">Reference / sanction number<input value={draft.reference_number || ""} onChange={(event) => setText("reference_number", event.target.value)} /></label>
        <label className="field">Proposal submission date<input type="date" value={draft.proposal_submission_date || ""} onChange={(event) => setText("proposal_submission_date", event.target.value)} /></label>
        <label className="field">Sanction / approval date<input type="date" value={draft.sanction_date || ""} onChange={(event) => setText("sanction_date", event.target.value)} /></label>
        <label className="field">Project start date<input type="date" value={draft.start_date || ""} onChange={(event) => setText("start_date", event.target.value)} /></label>
        <label className="field">Project end date<input type="date" value={draft.end_date || ""} onChange={(event) => setText("end_date", event.target.value)} /></label>
      </div>
    </section>

    <section className="panel">
      <h2>Project investigators</h2>
      <p className="muted">Sponsored research and consultancy records need at least one PI-level investigator. Preserve the funding agency’s exact designation when it differs from the normalized role.</p>
      {draft.faculty.map((member, index) => { const mode = member.affiliation_type || (member.faculty_id ? "FACULTY_MASTER" : "MANUAL"); const showManualFields = mode === "MANUAL" && (manualInvestigatorsAllowed || Boolean(member.investigator_name)); const historicalRole = legacyRoleLabels[member.role]; return <div className="author-card" key={member.id || index}><div className="split">
        {historicalRole ? <div className="field"><span>Investigator role</span><p className="muted">{historicalRole}<br /><small>This preserved historical designation cannot be selected for new investigators.</small></p></div> : <label className="field">Investigator role<select value={member.role} onChange={(event) => changeFaculty(index, "role", event.target.value)}>{facultyRoles.map((role) => <option key={role} value={role}>{roleLabels[role]}</option>)}</select></label>}
        {manualInvestigatorsAllowed && <label className="field">Investigator source<select value={mode} onChange={(event) => changeInvestigatorMode(index, event.target.value as "FACULTY_MASTER" | "MANUAL")}><option value="FACULTY_MASTER">Faculty Master</option><option value="MANUAL">Enter investigator details</option></select></label>}
        {showManualFields ? <>
          <label className="field wide">Investigator name *<input required value={member.investigator_name || ""} onChange={(event) => changeFaculty(index, "investigator_name", event.target.value)} /></label>
          <label className="field">Department<input value={member.department_name || ""} onChange={(event) => changeFaculty(index, "department_name", event.target.value)} /></label>
          <label className="field">Institution / organization<input value={member.institution_name || ""} onChange={(event) => changeFaculty(index, "institution_name", event.target.value)} /></label>
        </> : <FacultySelector label={`${member.role === "LEAD_PI" ? "Lead Principal Investigator" : member.role === "MEMBER_PI" ? "Member Principal Investigator" : member.role === "CO_PI" ? "Co-Principal Investigator" : member.role === "ADMIN_PI" ? "Administrative PI" : member.role === "BENEFICIARY" ? "Beneficiary" : historicalRole} ${index + 1}`} value={member.faculty_id || null} onChange={(value) => changeFaculty(index, "faculty_id", value)} faculty={masters?.faculty} loading={!masters && !error} error={!masters ? error : undefined} />}
        <label className="field">Designation in Sanction Letter (Optional)<input placeholder="For example: Member PI" value={member.agency_role_label || ""} onChange={(event) => changeFaculty(index, "agency_role_label", event.target.value)} /></label>
      </div><div className="actions"><button type="button" className="secondary small" disabled={index === 0} onClick={() => moveInvestigator(index, -1)}>Move up</button><button type="button" className="secondary small" disabled={index === draft.faculty.length - 1} onClick={() => moveInvestigator(index, 1)}>Move down</button><button type="button" className="secondary small" onClick={() => setDraft({ ...draft, faculty: draft.faculty.filter((_, current) => current !== index) })}>Remove investigator</button></div></div>; })}
      <button type="button" className="secondary" onClick={() => setDraft({ ...draft, faculty: [...draft.faculty, { faculty_id: null, role: draft.faculty.some((member) => piLevelRoles.has(member.role)) ? (category === "INTERNAL_GRANT" ? "BENEFICIARY" : "CO_PI") : "MEMBER_PI", affiliation_type: "FACULTY_MASTER", is_designated_lead: false }] })}>+ Add investigator</button>
    </section>

    <section className="panel">
      <h2>Financials and outcomes</h2>
      {category === "SPONSORED_RESEARCH" && <p className="muted">Proposed and sanctioned amounts are independent. Only sanctioned, ongoing, or completed projects with a sanctioned amount contribute to award KPIs.</p>}
      {category === "CONSULTANCY" && <p className="muted">Record the approved contract amount separately from amounts actually received.</p>}
      {category === "INTERNAL_GRANT" && <p className="muted">Record the sanctioned amount separately from the amount utilized. Leave either blank when it is not yet known.</p>}
      {historicalPreSanctionAmount && <p className="error" role="note">This pre-sanction record has a historical value in the sanctioned-amount field. It has not been reclassified or included in award KPIs; confirm its meaning before changing it.</p>}
      <div className="split">
        {financialFields.map(([caption, key]) => <label className="field" key={key}>{caption}<input type="number" min="0" step="0.01" inputMode="decimal" value={asInput(draft[key as keyof FundingProject] as string | number | null)} onChange={(event) => setText(key as keyof FundingProject, event.target.value)} /></label>)}
        <label className="field">Source URL<input type="url" value={draft.source_url || ""} onChange={(event) => setText("source_url", event.target.value)} /></label>
        <label className="field wide">Description<textarea rows={4} value={draft.description || ""} onChange={(event) => setText("description", event.target.value)} /></label>
        <label className="field wide">Deliverables<textarea rows={3} value={draft.deliverables || ""} onChange={(event) => setText("deliverables", event.target.value)} /></label>
        <label className="field wide">Outcomes<textarea rows={4} value={draft.outcomes || ""} onChange={(event) => setText("outcomes", event.target.value)} /></label>
        <label className="field wide">Completion details<textarea rows={3} value={draft.completion_details || ""} onChange={(event) => setText("completion_details", event.target.value)} /></label>
        <label className="field wide">Internal notes<textarea rows={3} value={draft.internal_notes || ""} onChange={(event) => setText("internal_notes", event.target.value)} /></label>
      </div>
    </section>
    <div className="savebar"><button disabled={busy}>{busy ? "Saving…" : draft.id ? "Save changes" : "Save project"}</button></div>
  </form>;
}
