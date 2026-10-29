"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, label, Masters } from "@/lib/api";
import FacultySelector from "@/components/FacultySelector";

export type Certification = {
  id?: number; faculty_id: number; name: string; category: string; provider: string;
  course_url?: string | null; credential_id?: string | null; issue_date?: string | null;
  completion_date?: string | null; expiry_date?: string | null; grade_score?: string | null;
  grade_scale?: string | null; status: string; notes?: string | null;
};

const categoryLabels: Record<string, string> = { NPTEL_SWAYAM: "NPTEL / SWAYAM", MOOC: "MOOC", OTHER: "Other Certifications" };
const newCategories = ["NPTEL_SWAYAM", "MOOC", "OTHER"];
const emptyCertification = (): Certification => ({ faculty_id: 0, name: "", category: "NPTEL_SWAYAM", provider: "", status: "COMPLETED", course_url: null, credential_id: null, issue_date: null, completion_date: null, expiry_date: null, grade_score: null, grade_scale: null, notes: null });

export default function CertificationEditor({ initial, onSaved }: { initial?: Certification; onSaved?: (row: Certification) => void }) {
  const router = useRouter();
  const [draft, setDraft] = useState<Certification>(initial || emptyCertification());
  const [masters, setMasters] = useState<Masters>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { setDraft(initial || emptyCertification()); }, [initial]);
  useEffect(() => { api<Masters>("/masters").then(setMasters).catch((requestError: Error) => setError(requestError.message)); }, []);

  function patch(values: Partial<Certification>) { setDraft((current) => ({ ...current, ...values })); }
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!draft.faculty_id) { setError("Select a Faculty Master record."); return; }
    setBusy(true); setError("");
    try {
      const { id, ...payload } = draft;
      const saved = await api<Certification>(id ? "/certifications/" + id : "/certifications", { method: id ? "PUT" : "POST", body: JSON.stringify(payload) });
      if (onSaved) { if (!id) setDraft(emptyCertification()); onSaved(saved); } else router.push("/certifications/" + saved.id);
    } catch (requestError) { setError((requestError as Error).message); } finally { setBusy(false); }
  }
  function text(key: keyof Certification, title: string, type = "text") {
    return <label><span>{title}</span><input type={type} value={String(draft[key] || "")} onChange={(event) => patch({ [key]: event.target.value || null })} /></label>;
  }

  return <form className="form-grid" onSubmit={save}>
    {error && <div className="error wide" role="alert">{error}</div>}
    <section className="panel wide"><h2>Faculty and certification details</h2><div className="grid">
      <FacultySelector label="Faculty" value={draft.faculty_id || null} onChange={(value) => patch({ faculty_id: value || 0 })} faculty={masters?.faculty} loading={!masters && !error} error={!masters ? error : undefined} />
      {text("name", "Course / certification name")}{text("provider", "Provider")}
      <label><span>Category</span><select value={draft.category} onChange={(event) => patch({ category: event.target.value })}>{newCategories.map((value) => <option key={value} value={value}>{categoryLabels[value]}</option>)}</select></label>
      <label><span>Status</span><select value={draft.status} onChange={(event) => patch({ status: event.target.value, ...(event.target.value === "IN_PROGRESS" ? { completion_date: null } : {}) })}><option value="COMPLETED">Completed</option><option value="IN_PROGRESS">In progress</option></select></label>
    </div></section>
    <section className="panel wide"><h2>Certification dates</h2><div className="grid">
      {(["issue_date", "completion_date", "expiry_date"] as const).map((key) => <label key={key}><span>{label(key)}</span><input required={key === "completion_date" && draft.status === "COMPLETED"} type="date" value={draft[key] || ""} onChange={(event) => patch({ [key]: event.target.value || null })} /></label>)}
    </div>{draft.status === "IN_PROGRESS" && <p className="muted">Current work does not require a completion date.</p>}</section>
    <section className="panel wide"><h2>Credential details</h2><div className="grid">
      {text("credential_id", "Credential ID")}{text("course_url", "Verification URL", "url")}{text("grade_score", "Grade / score")}{text("grade_scale", "Grade scale")}
      <label className="wide"><span>Notes</span><textarea value={draft.notes || ""} onChange={(event) => patch({ notes: event.target.value || null })} /></label>
    </div></section>
    <div className="savebar wide"><button disabled={busy}>{busy ? "Saving…" : draft.id ? "Save changes" : "Save certification"}</button></div>
  </form>;
}
