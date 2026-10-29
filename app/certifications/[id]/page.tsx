"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, label } from "@/lib/api";
import EvidenceManager from "@/components/EvidenceManager";

const categoryLabels: Record<string, string> = {
  NPTEL_SWAYAM: "NPTEL / SWAYAM",
  MOOC: "MOOC",
  OTHER: "Other Certifications",
};

export default function Page() {
  const { id } = useParams<{ id: string }>();
  const [row, setRow] = useState<any>();
  const [error, setError] = useState("");

  useEffect(() => {
    api<any>(`/certifications/${id}`).then(setRow).catch((reason) => setError(reason.message));
  }, [id]);

  if (error) return <><Link href="/certifications">← Certifications</Link><div className="error">{error}</div></>;
  if (!row) return <p role="status">Loading certification…</p>;

  const fields = [
    ["Category", categoryLabels[row.category] || label(row.category)],
    ["Issue date", row.issue_date],
    ["Completion date", row.completion_date],
    ["Expiry date", row.expiry_date],
    ["Credential ID", row.credential_id],
    ["Grade", row.grade_score],
    ["Status", label(row.status)],
  ];

  return <>
    <Link href="/certifications">← Certifications</Link>
    <div className="page-heading">
      <div><div className="eyebrow">{label(row.status)}</div><h1>{row.name}</h1><p>{row.faculty_name} · {row.provider}</p></div>
      <Link className="button" href={`/certifications/${id}/edit`}>Edit certification</Link>
    </div>
    <section className="panel">
      <dl className="detail-grid">
        {fields.map(([key, value]) => <div key={String(key)}><dt>{key}</dt><dd>{value || "—"}</dd></div>)}
      </dl>
      <p>{row.notes}</p>
    </section>
    <EvidenceManager entity="certifications" id={Number(id)} categories={["CERTIFICATE", "CREDENTIAL_PROOF", "OTHER"]} />
  </>;
}
