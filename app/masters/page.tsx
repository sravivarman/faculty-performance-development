"use client";

import { FormEvent, useEffect, useState } from "react";
import DeleteConfirmationDialog from "@/components/DeleteConfirmationDialog";
import { api, label, Masters, Person, Year } from "@/lib/api";

type MasterKind = "faculty" | "students" | "academic-years";
type MasterRecord = Person | Year;

function displayName(kind: MasterKind, record: MasterRecord) {
  if (kind === "academic-years") return record.name;
  const person = record as Person;
  return `${person.name} (${person.employee_id || person.roll_number || "no identifier"})`;
}

export default function MasterPage() {
  const [masters, setMasters] = useState<Masters>();
  const [kind, setKind] = useState<MasterKind>("faculty");
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<number>();
  const [deleting, setDeleting] = useState<MasterRecord>();
  const [error, setError] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = () => api<Masters>("/masters").then(setMasters);
  useEffect(() => { refresh().catch((reason) => setError((reason as Error).message)); }, []);

  const fields = kind === "faculty"
    ? ["employee_id", "name", "designation", "orcid", "scopus_author_id", "name_variants", "weak_name_variants"]
    : kind === "students" ? ["roll_number", "name", "batch", "program", "year_of_study", "name_variants"] : ["name", "start_date", "end_date"];
  const rows: MasterRecord[] = kind === "faculty" ? masters?.faculty || [] : kind === "students" ? masters?.students || [] : masters?.academic_years || [];

  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const payload: Record<string, unknown> = { ...draft };
      if (kind !== "academic-years") {
        payload.name_variants = (draft.name_variants || "").split("\n").map((value) => value.trim()).filter(Boolean);
        payload.is_active = draft.is_active !== "false";
        if (kind === "faculty") payload.name_variant_strengths = Object.fromEntries((draft.weak_name_variants || "").split("\n").map((value) => value.trim()).filter(Boolean).map((value) => [value, "WEAK"]));
      }
      for (const field of fields) if (!payload[field]) payload[field] = null;
      if (kind === "students") payload.year_of_study = draft.year_of_study ? Number(draft.year_of_study) : null;
      await api(`/${kind}${editing ? `/${editing}` : ""}`, { method: editing ? "PUT" : "POST", body: JSON.stringify(payload) });
      await refresh(); setDraft({}); setEditing(undefined); setNotice("Master record saved.");
    } catch (reason) { setError((reason as Error).message); } finally { setBusy(false); }
  }

  function edit(record: MasterRecord) {
    setEditing(record.id);
    setDraft(Object.fromEntries(Object.entries(record).map(([key, value]) => [key, ["name_variants", "weak_name_variants"].includes(key) ? (value as string[]).join("\n") : value === null || value === undefined ? "" : String(value)])));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function toggleActive(record: Person) {
    setBusy(true); setError("");
    try {
      const path = kind === "faculty" ? "/faculty" : "/students";
      await api(`${path}/${record.id}`, { method: "PUT", body: JSON.stringify({ ...record, is_active: !record.is_active }) });
      await refresh(); setNotice(`${record.name} ${record.is_active ? "deactivated" : "reactivated"}. Historical associations were retained.`);
    } catch (reason) { setError((reason as Error).message); } finally { setBusy(false); }
  }

  async function permanentlyDelete() {
    if (!deleting) return;
    setBusy(true); setDeleteError("");
    try {
      await api(`/${kind}/${deleting.id}`, { method: "DELETE" });
      await refresh(); setNotice(`${displayName(kind, deleting)} was deleted.`); setDeleting(undefined);
      if (editing === deleting.id) { setEditing(undefined); setDraft({}); }
    } catch (reason) { setDeleteError((reason as Error).message); } finally { setBusy(false); }
  }

  function changeKind(next: MasterKind) { setKind(next); setDraft({}); setEditing(undefined); setDeleting(undefined); setError(""); setNotice(""); }

  return <>
    <div className="eyebrow">Department directory</div><h1>Master records</h1>
    <p className="muted">Maintain author identities, name variants and academic-year boundaries. Records with historical references can be deactivated, but not permanently deleted.</p>
    {error && <div className="error" role="alert">{error}</div>}{notice && <div className="notice" role="status">{notice}</div>}
    <section className="panel">
      <div className="actions">{(["faculty", "students", "academic-years"] as MasterKind[]).map((value) => <button key={value} className={kind === value ? "" : "secondary"} onClick={() => changeKind(value)}>{label(value.replace("-", "_"))}</button>)}</div>
      <h2 style={{ marginTop: 25 }}>{editing ? "Edit" : "Add"} {kind === "academic-years" ? "academic year" : kind === "students" ? "student" : "faculty member"}</h2>
      <form onSubmit={save}><div className="grid">{fields.map((field) => <label key={field} className="field">{field === "weak_name_variants" ? "Weak aliases (review required)" : label(field)}
        {["name_variants", "weak_name_variants"].includes(field)
          ? <textarea aria-label={field === "weak_name_variants" ? "Weak aliases (review required)" : label(field)} placeholder="One variant per line" value={draft[field] || ""} onChange={(event) => setDraft({ ...draft, [field]: event.target.value })}/>
          : <input type={field.endsWith("date") ? "date" : field === "year_of_study" ? "number" : "text"} required={["name", "employee_id", "roll_number", "start_date", "end_date"].includes(field)} value={draft[field] || ""} onChange={(event) => setDraft({ ...draft, [field]: event.target.value })}/>}</label>)}</div>
        {kind !== "academic-years" && <label className="check" style={{ marginTop: 20 }}><input type="checkbox" checked={draft.is_active !== "false"} onChange={(event) => setDraft({ ...draft, is_active: String(event.target.checked) })}/>Active</label>}
        {kind === "academic-years" && <p className="muted">Use a full 12-month interval starting on the first of a month. Existing years cannot overlap. July–June years are preloaded.</p>}
        {kind === "faculty" && <p className="muted">Name variants lists all approved aliases. List weaker aliases again under Weak aliases; these always require review and never automatically assign an author.</p>}
        <div className="actions" style={{ marginTop: 20 }}><button disabled={busy}>Save master record</button>{editing && <button type="button" className="secondary" disabled={busy} onClick={() => { setEditing(undefined); setDraft({}); }}>Cancel edit</button>}</div>
      </form>
    </section>
    <section className="panel"><h2>{label(kind.replace("-", "_"))}</h2><div className="table-wrap"><table><thead><tr><th>Name</th><th>Identifier / Dates</th><th>Status</th><th>Actions</th></tr></thead><tbody>
      {rows.map((record) => {
        const isYear = kind === "academic-years"; const person = record as Person;
        return <tr key={record.id}><td>{record.name}{!isYear && <small>{person.name_variants.join(" · ")}{!!person.weak_name_variants?.length && <span> · Weak (review required): {person.weak_name_variants.join(" · ")}</span>}</small>}</td><td>{isYear ? `${(record as Year).start_date} – ${(record as Year).end_date}` : person.employee_id || person.roll_number}</td><td>{isYear ? "Configured" : person.is_active ? "Active" : "Inactive"}</td><td className="actions"><button className="secondary small" disabled={busy} onClick={() => edit(record)}>Edit</button>{!isYear && <button className="secondary small" disabled={busy} onClick={() => toggleActive(person)}>{person.is_active ? "Deactivate" : "Reactivate"}</button>}<button className="danger small" disabled={busy} onClick={() => { setDeleteError(""); setDeleting(record); }}>Delete</button></td></tr>;
      })}
      {!rows.length && <tr><td colSpan={4} className="empty">No {label(kind.replace("-", "_"))} records found.</td></tr>}
    </tbody></table></div></section>
    <DeleteConfirmationDialog open={!!deleting} title={`Delete ${kind === "academic-years" ? "Academic Year" : kind === "students" ? "Student" : "Faculty Member"}?`} recordName={deleting ? displayName(kind, deleting) : ""} description="This is permanent. The system will refuse deletion if the record is referenced by historical publications, activities, projects, or other records." busy={busy} error={deleteError} onCancel={() => { if (!busy) { setDeleting(undefined); setDeleteError(""); } }} onConfirm={permanentlyDelete}/>
  </>;
}
