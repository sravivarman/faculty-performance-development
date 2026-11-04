"use client";

import { FormEvent, useEffect, useState } from "react";
import DeleteConfirmationDialog from "@/components/DeleteConfirmationDialog";
import { api, Department, label, Masters, Person, Year } from "@/lib/api";

type MasterKind = "faculty" | "students" | "academic-years" | "departments";
type MasterRecord = Person | Year | Department;

const today = () => new Date().toISOString().slice(0, 10);

function displayName(kind: MasterKind, record: MasterRecord) {
  if (kind === "academic-years") return record.name;
  if (kind === "departments") {
    const department = record as Department;
    return department.name + " (" + department.code + ")";
  }
  const person = record as Person;
  return person.name + " (" + (person.employee_id || person.roll_number || "no identifier") + ")";
}

function departmentName(person: Person) {
  if (!person.department) return "Not assigned";
  return person.department.name + " (" + person.department.code + ")" + (person.department.is_active ? "" : " · inactive");
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
  const [transferDepartmentId, setTransferDepartmentId] = useState("");
  const [transferDate, setTransferDate] = useState(today());

  const refresh = () => api<Masters>("/masters").then(setMasters);
  useEffect(() => {
    refresh().catch((reason) => setError((reason as Error).message));
  }, []);

  const fields = kind === "faculty"
    ? ["employee_id", "name", "designation", "orcid", "scopus_author_id", "name_variants", "weak_name_variants"]
    : kind === "students"
      ? ["roll_number", "name", "batch", "program", "year_of_study", "name_variants"]
      : kind === "academic-years" ? ["name", "start_date", "end_date"] : ["code", "name"];
  const rows: MasterRecord[] = kind === "faculty" ? masters?.faculty || []
    : kind === "students" ? masters?.students || []
      : kind === "academic-years" ? masters?.academic_years || [] : masters?.departments || [];
  const isPerson = kind === "faculty" || kind === "students";
  const activeDepartments = masters?.departments.filter((department) => department.is_active) || [];

  function toDraft(record: MasterRecord) {
    return Object.fromEntries(Object.entries(record).map(([key, value]) => [
      key,
      ["name_variants", "weak_name_variants"].includes(key)
        ? (value as string[]).join("\n")
        : value === null || value === undefined || typeof value === "object" ? "" : String(value),
    ]));
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setNotice("");
    try {
      const payload: Record<string, unknown> = { ...draft };
      if (isPerson) {
        payload.name_variants = (draft.name_variants || "").split("\n").map((value) => value.trim()).filter(Boolean);
        payload.is_active = draft.is_active !== "false";
        payload.department_id = draft.department_id ? Number(draft.department_id) : null;
        if (kind === "faculty") {
          payload.name_variant_strengths = Object.fromEntries(
            (draft.weak_name_variants || "").split("\n").map((value) => value.trim()).filter(Boolean).map((value) => [value, "WEAK"]),
          );
          if (!editing) payload.department_effective_from = draft.department_effective_from || today();
        }
      }
      for (const field of fields) if (!payload[field]) payload[field] = null;
      if (kind === "students") payload.year_of_study = draft.year_of_study ? Number(draft.year_of_study) : null;
      await api("/" + kind + (editing ? "/" + editing : ""), {
        method: editing ? "PUT" : "POST",
        body: JSON.stringify(payload),
      });
      await refresh();
      setDraft({}); setEditing(undefined);
      setNotice("Master record saved.");
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function edit(record: MasterRecord) {
    setEditing(record.id);
    setDraft(toDraft(record));
    setTransferDepartmentId("");
    setTransferDate(today());
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function transferFaculty() {
    if (!editing || !transferDepartmentId) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await api<Person>("/faculty/" + editing + "/department-transfer", {
        method: "POST",
        body: JSON.stringify({ department_id: Number(transferDepartmentId), effective_from: transferDate }),
      });
      await refresh();
      setDraft(toDraft(result));
      setTransferDepartmentId("");
      setNotice("Faculty Department transferred. Previous affiliation history was retained.");
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(record: MasterRecord) {
    setBusy(true); setError("");
    try {
      if (kind === "departments") {
        const department = record as Department;
        await api("/departments/" + department.id + "/" + (department.is_active ? "deactivate" : "reactivate"), { method: "POST" });
      } else {
        const person = record as Person;
        const path = kind === "faculty" ? "/faculty" : "/students";
        await api(path + "/" + record.id, {
          method: "PUT",
          body: JSON.stringify({ ...person, is_active: !person.is_active }),
        });
      }
      await refresh();
      setNotice(displayName(kind, record) + " " + ((record as Person | Department).is_active ? "deactivated" : "reactivated") + ". Historical associations were retained.");
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function permanentlyDelete() {
    if (!deleting) return;
    setBusy(true); setDeleteError("");
    try {
      await api("/" + kind + "/" + deleting.id, { method: "DELETE" });
      await refresh();
      setNotice(displayName(kind, deleting) + " was deleted.");
      setDeleting(undefined);
      if (editing === deleting.id) {
        setEditing(undefined);
        setDraft({});
      }
    } catch (reason) {
      setDeleteError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function changeKind(next: MasterKind) {
    setKind(next); setDraft({}); setEditing(undefined); setDeleting(undefined); setError(""); setNotice("");
  }

  function renderDepartmentSelect(labelText: string, value: string, onChange: (value: string) => void, allowCurrentInactive = false) {
    const current = masters?.departments.find((department) => String(department.id) === value);
    const choices = current && !current.is_active && allowCurrentInactive ? [current, ...activeDepartments] : activeDepartments;
    return <label className="field">{labelText}<select required value={value} onChange={(event) => onChange(event.target.value)}>
      <option value="">Select Department</option>
      {choices.map((department) => <option key={department.id} value={department.id}>
        {department.name} ({department.code}){department.is_active ? "" : " · inactive"}
      </option>)}
    </select></label>;
  }

  const editedFaculty = kind === "faculty" && editing
    ? rows.find((record) => record.id === editing) as Person | undefined : undefined;
  const deleteTitle = kind === "academic-years" ? "Academic Year"
    : kind === "students" ? "Student" : kind === "departments" ? "Department" : "Faculty Member";

  return <>
    <div className="eyebrow">Institutional master directory</div><h1>Master records</h1>
    <p className="muted">Maintain Department, Faculty, Student, and Academic Year master records. Historical references remain protected from permanent deletion.</p>
    {error && <div className="error" role="alert">{error}</div>}
    {notice && <div className="notice" role="status">{notice}</div>}
    <section className="panel">
      <div className="actions">
        {(["faculty", "students", "departments", "academic-years"] as MasterKind[]).map((value) =>
          <button key={value} className={kind === value ? "" : "secondary"} onClick={() => changeKind(value)}>
            {label(value.replace("-", "_"))}
          </button>,
        )}
      </div>
      <h2 style={{ marginTop: 25 }}>
        {editing ? "Edit" : "Add"} {kind === "academic-years" ? "academic year" : kind === "students" ? "student" : kind === "departments" ? "Department" : "Faculty member"}
      </h2>
      <form onSubmit={save}>
        <div className="grid">
          {fields.map((field) => <label key={field} className="field">
            {field === "weak_name_variants" ? "Weak aliases (review required)" : label(field)}
            {["name_variants", "weak_name_variants"].includes(field)
              ? <textarea aria-label={field === "weak_name_variants" ? "Weak aliases (review required)" : label(field)} placeholder="One variant per line" value={draft[field] || ""} onChange={(event) => setDraft({ ...draft, [field]: event.target.value })}/>
              : <input type={field.endsWith("date") ? "date" : field === "year_of_study" ? "number" : "text"} required={["name", "employee_id", "roll_number", "start_date", "end_date", "code"].includes(field)} value={draft[field] || ""} onChange={(event) => setDraft({ ...draft, [field]: event.target.value })}/>}
          </label>)}
        </div>
        {kind === "faculty" && !editing && <div className="grid" style={{ marginTop: 16 }}>
          {renderDepartmentSelect("Current Department", draft.department_id || "", (value) => setDraft({ ...draft, department_id: value }))}
          <label className="field">Department effective from<input type="date" required value={draft.department_effective_from || today()} onChange={(event) => setDraft({ ...draft, department_effective_from: event.target.value })}/></label>
        </div>}
        {kind === "students" && <div className="grid" style={{ marginTop: 16 }}>
          {renderDepartmentSelect("Primary Department", draft.department_id || "", (value) => setDraft({ ...draft, department_id: value }), Boolean(editing))}
        </div>}
        {isPerson && <label className="check" style={{ marginTop: 20 }}><input type="checkbox" checked={draft.is_active !== "false"} onChange={(event) => setDraft({ ...draft, is_active: String(event.target.checked) })}/>Active</label>}
        {kind === "academic-years" && <p className="muted">Use a full 12-month interval starting on the first of a month. Existing years cannot overlap.</p>}
        {kind === "faculty" && <p className="muted">Name variants list approved aliases. Weak aliases always require review and never automatically assign an author.</p>}
        <div className="actions" style={{ marginTop: 20 }}>
          <button disabled={busy}>Save master record</button>
          {editing && <button type="button" className="secondary" disabled={busy} onClick={() => { setEditing(undefined); setDraft({}); }}>Cancel edit</button>}
        </div>
      </form>
      {editedFaculty && <section className="panel" style={{ marginTop: 24 }}>
        <h3>Department history</h3>
        <p className="muted">A transfer closes the current primary affiliation on the day before the transfer date. Migration-baseline entries retain an unknown historical start date.</p>
        <div className="table-wrap"><table><thead><tr><th>Department</th><th>From</th><th>To</th><th>Source</th></tr></thead><tbody>
          {editedFaculty.department_history?.map((affiliation) => <tr key={affiliation.id}>
            <td>{affiliation.department?.name || "Unknown Department"} ({affiliation.department?.code || affiliation.department_id})</td>
            <td>{affiliation.effective_from || "Unknown historical start"}</td><td>{affiliation.effective_to || "Current"}</td><td>{label(affiliation.source)}</td>
          </tr>)}
        </tbody></table></div>
        <div className="grid" style={{ marginTop: 16 }}>
          {renderDepartmentSelect("Transfer to Department", transferDepartmentId, setTransferDepartmentId)}
          <label className="field">Transfer effective from<input type="date" required value={transferDate} onChange={(event) => setTransferDate(event.target.value)}/></label>
        </div>
        <button type="button" disabled={busy || !transferDepartmentId} onClick={transferFaculty}>Transfer Department</button>
      </section>}
    </section>
    <section className="panel"><h2>{label(kind.replace("-", "_"))}</h2><div className="table-wrap"><table><thead><tr><th>Name</th><th>Identifier / Department / Dates</th><th>Status</th><th>Actions</th></tr></thead><tbody>
      {rows.map((record) => {
        const isYear = kind === "academic-years";
        const isDepartment = kind === "departments";
        const person = record as Person;
        const department = record as Department;
        const active = (record as Person | Department).is_active;
        return <tr key={record.id}>
          <td>{record.name}{!isYear && !isDepartment && <small>{person.name_variants.join(" · ")}{!!person.weak_name_variants?.length && <span> · Weak (review required): {person.weak_name_variants.join(" · ")}</span>}</small>}</td>
          <td>{isYear ? (record as Year).start_date + " – " + (record as Year).end_date : isDepartment ? <>{department.code}<small>{department.faculty_count || 0} current Faculty · {department.student_count || 0} Students</small></> : <>{person.employee_id || person.roll_number}<small>{departmentName(person)}</small></>}</td>
          <td>{isYear ? "Configured" : active ? "Active" : "Inactive"}</td>
          <td className="actions"><button className="secondary small" disabled={busy} onClick={() => edit(record)}>Edit</button>{!isYear && <button className="secondary small" disabled={busy} onClick={() => toggleActive(record)}>{active ? "Deactivate" : "Reactivate"}</button>}<button className="danger small" disabled={busy} onClick={() => { setDeleteError(""); setDeleting(record); }}>Delete</button></td>
        </tr>;
      })}
      {!rows.length && <tr><td colSpan={4} className="empty">No {label(kind.replace("-", "_"))} records found.</td></tr>}
    </tbody></table></div></section>
    <DeleteConfirmationDialog open={!!deleting} title={"Delete " + deleteTitle + "?"} recordName={deleting ? displayName(kind, deleting) : ""} description="This is permanent. The system will refuse deletion if the record is referenced by historical research records, Department affiliations, or Student assignments." busy={busy} error={deleteError} onCancel={() => { if (!busy) { setDeleting(undefined); setDeleteError(""); } }} onConfirm={permanentlyDelete}/>
  </>;
}
