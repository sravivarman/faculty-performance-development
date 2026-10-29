"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api, label } from "@/lib/api";
import EvidenceManager from "@/components/EvidenceManager";

type Activity = any;
const categories = ["CERTIFICATE", "COMPLETION_LETTER", "PROGRAM", "REPORT", "OTHER"];
const activityTypeLabels: Record<string, string> = { FDP: "FDP", STTP: "STTP", WORKSHOP: "Workshop", WEBINAR: "Webinar", SEMINAR: "Seminar", INTERNSHIP: "Internship", INDUSTRIAL_TRAINING: "Industrial Training" };

export default function Page() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [row, setRow] = useState<Activity>();
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteText, setDeleteText] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => {
    setError("");
    api<Activity>(`/fdp-activities/${id}`).then(setRow).catch((reason) => setError(reason.message));
  };
  useEffect(load, [id]);

  async function deactivate() {
    if (!confirm("Deactivate this activity? Its participants, speakers, evidence, and history will be retained.")) return;
    setBusy(true);
    setError("");
    try {
      await api(`/fdp-activities/${id}`, { method: "DELETE" });
      setNotice("Activity deactivated. Its history and evidence remain available.");
      load();
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function reactivate() {
    setBusy(true);
    setError("");
    try {
      const restored = await api<Activity>(`/fdp-activities/${id}/reactivate`, { method: "POST" });
      setRow(restored);
      setNotice("Activity reactivated. It is included in active lists and KPIs again.");
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function permanentlyDelete() {
    if (deleteText !== "DELETE") return;
    setBusy(true);
    setError("");
    try {
      const result = await api<{ evidence_cleanup_failures: { filename: string }[] }>(`/fdp-activities/${id}/permanent`, { method: "DELETE" });
      if (result.evidence_cleanup_failures.length) {
        alert(`The activity was deleted, but ${result.evidence_cleanup_failures.length} evidence file(s) could not be removed from local storage. Please contact the system administrator.`);
      }
      router.push("/fdp");
      router.refresh();
    } catch (reason) {
      setError((reason as Error).message);
      setBusy(false);
    }
  }

  if (error && !row) return <><Link href="/fdp">← FDP activities</Link><div className="error">{error}</div></>;
  if (!row) return <p role="status">Loading activity…</p>;

  return <>
    <Link href="/fdp">← FDP activities</Link>
    <div className="page-heading">
      <div><div className="eyebrow">{activityTypeLabels[row.activity_type] || label(row.activity_type)} · {row.is_active ? "Active" : "Inactive"}</div><h1>{row.title}</h1><p>{row.organizing_institution}</p></div>
      <div className="actions">
        {row.is_active ? <><Link className="button" href={`/fdp/${id}/edit`}>Edit activity</Link><button className="secondary" disabled={busy} onClick={deactivate}>Deactivate</button></> : <button disabled={busy} onClick={reactivate}>Reactivate</button>}
        <button className="danger" disabled={busy} onClick={() => { setConfirmDelete(true); setDeleteText(""); }}>Permanently Delete</button>
      </div>
    </div>
    {error && <div className="error" role="alert">{error}</div>}
    {notice && <div className="notice" role="status">{notice}</div>}
    {confirmDelete && <section className="panel danger-panel" role="dialog" aria-modal="true" aria-labelledby="permanent-delete-title">
      <h2 id="permanent-delete-title">Permanently delete this activity?</h2>
      <p>This cannot be undone. The activity, its Faculty participation, speakers, change history, and activity-owned evidence records will be removed. Faculty Master records and other activities will not be changed.</p>
      <label className="field">Type <strong>DELETE</strong> to enable permanent deletion
        <input value={deleteText} onChange={(event) => setDeleteText(event.target.value)} autoComplete="off" />
      </label>
      <div className="actions"><button type="button" className="secondary" disabled={busy} onClick={() => { setConfirmDelete(false); setDeleteText(""); }}>Cancel</button><button type="button" className="danger" disabled={busy || deleteText !== "DELETE"} onClick={permanentlyDelete}>{busy ? "Deleting…" : "Permanently Delete"}</button></div>
    </section>}
    <section className="panel"><h2>Activity details</h2><dl className="detail-grid">{[["Start date", row.start_date], ["End date", row.end_date], ["Duration", `${row.duration_value} ${label(row.duration_unit)}`], ["Mode", row.mode && label(row.mode)], ["Location", row.location], ["Attendance", row.attendance_count]].map(([key, value]) => <div key={String(key)}><dt>{key}</dt><dd>{value || "—"}</dd></div>)}</dl><p>{row.description}</p><p><strong>Outcomes:</strong> {row.outcomes || "—"}</p></section>
    <section className="panel"><h2>Faculty participants</h2>{row.participants.map((participant: any) => <p key={participant.id}>{participant.faculty_name} · <span className="badge">{label(participant.role)}</span></p>)}</section>
    <section className="panel"><h2>Speakers</h2>{row.speakers.map((speaker: any) => <p key={speaker.id}><strong>{speaker.name}</strong>{speaker.designation && ` · ${speaker.designation}`}{speaker.organization && ` · ${speaker.organization}`}</p>)}{!row.speakers.length && <p className="muted">No speakers recorded.</p>}</section>
    <EvidenceManager entity="fdp-activities" id={Number(id)} categories={categories} />
  </>;
}
