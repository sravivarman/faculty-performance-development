"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, label, Masters } from "@/lib/api";
import FacultySelector from "@/components/FacultySelector";

type Participant = { faculty_id: number; role: string };
type Speaker = {
  name: string;
  designation?: string | null;
  organization?: string | null;
  location_or_contact?: string | null;
};

export type FdpActivity = {
  id?: number;
  title: string;
  activity_type: string;
  organizing_institution: string;
  start_date: string;
  end_date?: string | null;
  duration_value: number;
  duration_unit: string;
  location?: string | null;
  mode?: string | null;
  description?: string | null;
  source_url?: string | null;
  outcomes?: string | null;
  internal_notes?: string | null;
  attendance_count?: number | null;
  company_location?: string | null;
  participants: Participant[];
  speakers: Speaker[];
};

type Props = {
  initial?: FdpActivity;
  onSaved?: (activity: FdpActivity) => void;
};

const roles = ["ATTENDEE", "RESOURCE_PERSON", "COORDINATOR"];
const activityTypes = ["FDP", "STTP", "WORKSHOP", "WEBINAR", "SEMINAR", "INTERNSHIP", "INDUSTRIAL_TRAINING"];
const activityTypeLabels: Record<string, string> = { FDP: "FDP", STTP: "STTP", WORKSHOP: "Workshop", WEBINAR: "Webinar", SEMINAR: "Seminar", INTERNSHIP: "Internship", INDUSTRIAL_TRAINING: "Industrial Training" };

function emptyActivity(): FdpActivity {
  return {
    title: "",
    activity_type: "FDP",
    organizing_institution: "",
    start_date: "",
    end_date: null,
    duration_value: 1,
    duration_unit: "DAYS",
    location: null,
    mode: null,
    description: null,
    source_url: null,
    outcomes: null,
    internal_notes: null,
    attendance_count: null,
    company_location: null,
    participants: [],
    speakers: [],
  };
}

export default function FdpEditor({ initial, onSaved }: Props) {
  const router = useRouter();
  const [draft, setDraft] = useState<FdpActivity>(initial || emptyActivity());
  const [masters, setMasters] = useState<Masters>();
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkQuery, setBulkQuery] = useState("");
  const [bulkRole, setBulkRole] = useState("ATTENDEE");
  const [bulkSelected, setBulkSelected] = useState<number[]>([]);

  useEffect(() => {
    setDraft(initial || emptyActivity());
    setBulkOpen(false);
    setBulkQuery("");
    setBulkSelected([]);
  }, [initial]);
  useEffect(() => {
    api<Masters>("/masters").then(setMasters).catch((requestError: Error) => setError(requestError.message));
  }, []);

  function changeParticipant(index: number, key: keyof Participant, value: string) {
    const participants = draft.participants.map((participant, currentIndex) => currentIndex === index
      ? { ...participant, [key]: key === "faculty_id" ? Number(value) : value }
      : participant);
    const selected = participants[index];
    if (selected.faculty_id && participants.filter((participant) => participant.faculty_id === selected.faculty_id && participant.role === selected.role).length > 1) {
      setError("Duplicate Faculty-role combinations are not allowed.");
      return;
    }
    setError("");
    setNotice("");
    setDraft({ ...draft, participants });
  }

  const matchingFaculty = (masters?.faculty || []).filter((faculty) => {
    const searchable = (faculty.name + " " + (faculty.employee_id || "")).toLowerCase();
    return searchable.includes(bulkQuery.trim().toLowerCase());
  });
  const distinctParticipantCount = new Set(draft.participants.map((participant) => participant.faculty_id).filter(Boolean)).size;

  function closeBulkSelection() {
    setBulkOpen(false);
    setBulkQuery("");
    setBulkSelected([]);
  }

  function toggleBulkFaculty(identity: number) {
    setBulkSelected((current) => current.includes(identity)
      ? current.filter((selected) => selected !== identity)
      : [...current, identity]);
  }

  function applyBulkFaculty() {
    if (!bulkSelected.length) {
      setError("Select at least one Faculty member to add.");
      return;
    }
    const existing = new Set(draft.participants.map((participant) => participant.faculty_id + ":" + participant.role));
    const additions = bulkSelected
      .filter((identity) => !existing.has(identity + ":" + bulkRole))
      .map((faculty_id) => ({ faculty_id, role: bulkRole }));
    const skipped = bulkSelected.length - additions.length;
    if (!additions.length) {
      setError("Those Faculty-role associations are already listed.");
      return;
    }
    setDraft({ ...draft, participants: [...draft.participants, ...additions] });
    closeBulkSelection();
    setError("");
    setNotice(skipped
      ? `Added ${additions.length} Faculty-role association(s); ${skipped} duplicate association(s) were not added.`
      : `Added ${additions.length} Faculty-role association(s).`);
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (draft.participants.some((participant) => !participant.faculty_id)) {
      setError("Select a Faculty Master record for every participant.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const { id, ...payload } = draft;
      const saved = id
        ? await api<FdpActivity>("/fdp-activities/" + id, { method: "PUT", body: JSON.stringify(payload) })
        : await api<FdpActivity>("/fdp-activities", { method: "POST", body: JSON.stringify(payload) });
      if (onSaved) {
        if (!id) setDraft(emptyActivity());
        onSaved(saved);
      } else {
        router.push("/fdp/" + saved.id);
      }
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="fdp-editor" onSubmit={save}>
      {error && <div className="error" role="alert">{error}</div>}
      {notice && <div className="notice" role="status">{notice}</div>}

      <section className="panel">
        <h2>Activity details</h2>
        <p className="muted">Record the activity, organizer, schedule, delivery mode and venue.</p>
        <div className="split">
          <label className="field wide">Activity title *
            <input required value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} />
          </label>
          <label className="field">Activity type *
            <select value={draft.activity_type} onChange={(event) => setDraft({ ...draft, activity_type: event.target.value })}>
              {activityTypes.map((value) => <option key={value} value={value}>{activityTypeLabels[value]}</option>)}
            </select>
          </label>
          <label className="field">Mode
            <select value={draft.mode || ""} onChange={(event) => setDraft({ ...draft, mode: event.target.value || null })}>
              <option value="">Not specified</option>
              {["PHYSICAL", "ONLINE", "HYBRID"].map((value) => <option key={value} value={value}>{label(value)}</option>)}
            </select>
          </label>
          <label className="field">Organizing institution / company *
            <input required value={draft.organizing_institution} onChange={(event) => setDraft({ ...draft, organizing_institution: event.target.value })} />
          </label>
          <label className="field">Duration *
            <div className="fdp-duration">
              <input required aria-label="Duration value" type="number" min="0" step="any" value={draft.duration_value} onChange={(event) => {
                const value = event.target.value;
                event.currentTarget.setCustomValidity(value && Number(value) > 0 ? "" : "Duration must be greater than zero.");
                setDraft({ ...draft, duration_value: Number(value) });
              }} />
              <select aria-label="Duration unit" value={draft.duration_unit} onChange={(event) => setDraft({ ...draft, duration_unit: event.target.value })}>
                {["HOURS", "DAYS", "WEEKS", "MONTHS"].map((value) => <option key={value} value={value}>{label(value)}</option>)}
              </select>
            </div>
          </label>
          <label className="field">Start date *
            <input required type="date" value={draft.start_date} onChange={(event) => setDraft({ ...draft, start_date: event.target.value })} />
          </label>
          <label className="field">End date
            <input type="date" value={draft.end_date || ""} onChange={(event) => setDraft({ ...draft, end_date: event.target.value || null })} />
          </label>
          <label className="field">Location / venue
            <input value={draft.location || ""} onChange={(event) => setDraft({ ...draft, location: event.target.value || null })} />
          </label>
          <label className="field">Company location
            <input value={draft.company_location || ""} onChange={(event) => setDraft({ ...draft, company_location: event.target.value || null })} />
          </label>
        </div>
      </section>

      <section className="panel">
        <h2>Faculty participation</h2>
        <p className="muted">Each Faculty-and-role combination is retained separately; duplicate combinations are not allowed.</p>
        <p className="muted" aria-live="polite">{distinctParticipantCount} distinct Faculty member{distinctParticipantCount === 1 ? "" : "s"} · {draft.participants.length} Faculty-role association{draft.participants.length === 1 ? "" : "s"}</p>
        {draft.participants.length > 0 && <div className="fdp-participant-table" role="table" aria-label="Faculty participants">
          <div className="fdp-participant-header" role="row">
            <span role="columnheader">Faculty participant</span><span role="columnheader">Employee ID</span><span role="columnheader">Participation role</span><span role="columnheader">Action</span>
          </div>
          {draft.participants.map((participant, index) => {
            const faculty = masters?.faculty.find((person) => person.id === participant.faculty_id);
            return <div className="fdp-participant-row" role="row" key={index}>
              <div role="cell"><FacultySelector
                label={"Participant " + (index + 1)}
                value={participant.faculty_id || null}
                onChange={(value) => changeParticipant(index, "faculty_id", String(value || ""))}
                faculty={masters?.faculty}
                loading={!masters && !error}
                error={!masters ? error : undefined}
              /></div>
              <span className="fdp-employee-id" role="cell">{faculty?.employee_id || "—"}{faculty && !faculty.is_active ? " · Historical" : ""}</span>
              <label className="field" role="cell">Participation role
                <select value={participant.role} onChange={(event) => changeParticipant(index, "role", event.target.value)}>
                  {roles.map((value) => <option key={value} value={value}>{label(value)}</option>)}
                </select>
              </label>
              <div className="fdp-participant-action" role="cell"><button type="button" className="secondary small" onClick={() => setDraft({ ...draft, participants: draft.participants.filter((_, currentIndex) => currentIndex !== index) })}>Remove</button></div>
            </div>;
          })}
        </div>}
        <div className="actions">
          <button type="button" className="secondary" onClick={() => setDraft({ ...draft, participants: [...draft.participants, { faculty_id: 0, role: "ATTENDEE" }] })}>+ Add Faculty</button>
          <button type="button" className="secondary" onClick={() => setBulkOpen((open) => !open)}>+ Add Multiple Faculty</button>
        </div>
        {bulkOpen && <div className="fdp-bulk-selector">
          <div className="row-between"><div><h3>Add multiple Faculty</h3><p className="muted">Choose a common participation role, then add all selected Faculty to this activity.</p></div><button type="button" className="secondary small" onClick={closeBulkSelection}>Close</button></div>
          <div className="split">
            <label className="field">Search Faculty Master
              <input type="search" placeholder="Name or employee ID" value={bulkQuery} onChange={(event) => setBulkQuery(event.target.value)} />
            </label>
            <label className="field">Common participation role
              <select value={bulkRole} onChange={(event) => setBulkRole(event.target.value)}>{roles.map((value) => <option key={value} value={value}>{label(value)}</option>)}</select>
            </label>
          </div>
          <p className="muted" aria-live="polite">{bulkSelected.length} Faculty member{bulkSelected.length === 1 ? "" : "s"} selected.</p>
          <div className="fdp-bulk-list" role="group" aria-label="Faculty Master bulk selection">
            {!masters ? <p role="status">Loading Faculty Master…</p> : !matchingFaculty.length ? <p className="muted">No Faculty records match this search.</p> : matchingFaculty.map((faculty) => <label className="fdp-bulk-option" key={faculty.id}>
              <input type="checkbox" checked={bulkSelected.includes(faculty.id)} onChange={() => toggleBulkFaculty(faculty.id)} />
              <span><strong>{faculty.name}</strong>{faculty.employee_id ? ` · ${faculty.employee_id}` : ""}{!faculty.is_active ? " · Historical" : ""}</span>
            </label>)}
          </div>
          <div className="actions"><button type="button" className="secondary" onClick={() => setBulkSelected([])} disabled={!bulkSelected.length}>Clear selection</button><button type="button" disabled={!bulkSelected.length} onClick={applyBulkFaculty}>Add selected Faculty</button></div>
        </div>}
      </section>

      <section className="panel">
        <h2>Resource persons / speakers</h2>
        <p className="muted">External speakers do not require a Faculty Master record.</p>
        {draft.speakers.map((speaker, index) => (
          <div className="author-card fdp-speaker-card" key={index}>
            <div className="split">
              <label className="field">Speaker name *
                <input required value={speaker.name} onChange={(event) => setDraft({ ...draft, speakers: draft.speakers.map((current, currentIndex) => currentIndex === index ? { ...current, name: event.target.value } : current) })} />
              </label>
              <label className="field">Designation
                <input value={speaker.designation || ""} onChange={(event) => setDraft({ ...draft, speakers: draft.speakers.map((current, currentIndex) => currentIndex === index ? { ...current, designation: event.target.value || null } : current) })} />
              </label>
              <label className="field">Organization
                <input value={speaker.organization || ""} onChange={(event) => setDraft({ ...draft, speakers: draft.speakers.map((current, currentIndex) => currentIndex === index ? { ...current, organization: event.target.value || null } : current) })} />
              </label>
              <label className="field">Location / contact
                <input value={speaker.location_or_contact || ""} onChange={(event) => setDraft({ ...draft, speakers: draft.speakers.map((current, currentIndex) => currentIndex === index ? { ...current, location_or_contact: event.target.value || null } : current) })} />
              </label>
            </div>
            <div className="actions"><button type="button" className="secondary small" onClick={() => setDraft({ ...draft, speakers: draft.speakers.filter((_, currentIndex) => currentIndex !== index) })}>Remove speaker</button></div>
          </div>
        ))}
        <div className="actions"><button type="button" className="secondary" onClick={() => setDraft({ ...draft, speakers: [...draft.speakers, { name: "" }] })}>+ Add Speaker</button></div>
      </section>

      <section className="panel">
        <h2>Outcomes and additional information</h2>
        <div className="split">
          <label className="field">Attendance count
            <input type="number" min="0" value={draft.attendance_count ?? ""} onChange={(event) => setDraft({ ...draft, attendance_count: event.target.value ? Number(event.target.value) : null })} />
          </label>
          <label className="field">Source URL
            <input type="url" value={draft.source_url || ""} onChange={(event) => setDraft({ ...draft, source_url: event.target.value || null })} />
          </label>
          <label className="field wide">Description
            <textarea rows={4} value={draft.description || ""} onChange={(event) => setDraft({ ...draft, description: event.target.value || null })} />
          </label>
          <label className="field wide">Outcomes
            <textarea rows={4} value={draft.outcomes || ""} onChange={(event) => setDraft({ ...draft, outcomes: event.target.value || null })} />
          </label>
          <label className="field wide">Internal notes
            <textarea rows={4} value={draft.internal_notes || ""} onChange={(event) => setDraft({ ...draft, internal_notes: event.target.value || null })} />
          </label>
        </div>
      </section>

      <div className="savebar"><button disabled={busy}>{busy ? "Saving…" : draft.id ? "Save changes" : "Save activity"}</button></div>
    </form>
  );
}
