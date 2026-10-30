"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import FacultySelector from "@/components/FacultySelector";
import { api, label, Masters } from "@/lib/api";

export const fundingCategories = ["SPONSORED_RESEARCH", "CONSULTANCY", "INTERNAL_GRANT"] as const;
export const fundingStatuses = ["DRAFT", "SUBMITTED", "UNDER_REVIEW", "SANCTIONED", "ONGOING", "COMPLETED", "REJECTED", "WITHDRAWN"] as const;
const facultyRoles = ["PI", "CO_PI", "BENEFICIARY"] as const;

export type FundingFaculty = { faculty_id: number; role: string; faculty_name?: string };
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
  sanctioned_amount?: string | number | null;
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
  return { title: "", category, department: "", funding_agency: null, proposal_submission_date: null, sanction_date: null, start_date: null, end_date: null, sanctioned_amount: null, amount_received: null, amount_utilized: null, reference_number: null, status: "DRAFT", description: null, outcomes: null, deliverables: null, completion_details: null, internal_notes: null, source_url: null, faculty: [] };
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

  function changeFaculty(index: number, key: keyof FundingFaculty, value: string | number | null) {
    const faculty = draft.faculty.map((member, current) => current === index
      ? { ...member, [key]: key === "faculty_id" ? Number(value || 0) : value }
      : member);
    const current = faculty[index];
    if (current.faculty_id && faculty.filter((member) => member.faculty_id === current.faculty_id && member.role === current.role).length > 1) {
      setError("Duplicate Faculty-role associations are not allowed.");
      return;
    }
    setError("");
    setDraft({ ...draft, faculty });
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (draft.faculty.some((member) => !member.faculty_id)) {
      setError("Select a Faculty Master record for every project association.");
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
  const setText = (key: keyof FundingProject, value: string) => setDraft({ ...draft, [key]: value || null });

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
      <h2>Faculty association</h2>
      <p className="muted">Select exactly one Principal Investigator. Co-PIs and internal-grant beneficiaries may be added without creating duplicate project records.</p>
      {draft.faculty.map((member, index) => <div className="author-card" key={index}><div className="split">
        <FacultySelector label={`Faculty ${index + 1}`} value={member.faculty_id || null} onChange={(value) => changeFaculty(index, "faculty_id", value)} faculty={masters?.faculty} loading={!masters && !error} error={!masters ? error : undefined} />
        <label className="field">Project role<select value={member.role} onChange={(event) => changeFaculty(index, "role", event.target.value)}>{facultyRoles.map((role) => <option key={role} value={role}>{label(role)}</option>)}</select></label>
      </div><div className="actions"><button type="button" className="secondary small" onClick={() => setDraft({ ...draft, faculty: draft.faculty.filter((_, current) => current !== index) })}>Remove Faculty</button></div></div>)}
      <button type="button" className="secondary" onClick={() => setDraft({ ...draft, faculty: [...draft.faculty, { faculty_id: 0, role: draft.faculty.some((member) => member.role === "PI") ? "CO_PI" : "PI" }] })}>+ Add Faculty</button>
    </section>

    <section className="panel">
      <h2>Financials and outcomes</h2>
      <div className="split">
        {[ ["Sanctioned amount (INR)", "sanctioned_amount"], ["Amount received (INR)", "amount_received"], ["Amount utilized (INR)", "amount_utilized"] ].map(([caption, key]) => <label className="field" key={key}>{caption}<input type="number" min="0" step="0.01" inputMode="decimal" value={asInput(draft[key as keyof FundingProject] as string | number | null)} onChange={(event) => setText(key as keyof FundingProject, event.target.value)} /></label>)}
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
