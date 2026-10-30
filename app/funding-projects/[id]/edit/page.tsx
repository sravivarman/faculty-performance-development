"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import EvidenceManager from "@/components/EvidenceManager";
import FundingEditor, { FundingProject } from "@/components/FundingEditor";
import { api } from "@/lib/api";

const evidenceTypes = ["PROPOSAL", "SANCTION_LETTER", "AGREEMENT", "FUNDING_RECEIPT", "UTILIZATION_CERTIFICATE", "PROGRESS_REPORT", "COMPLETION_REPORT", "OUTCOME_EVIDENCE", "OTHER"];

export default function EditFundingProjectPage() {
  const { id } = useParams<{ id: string }>();
  const [record, setRecord] = useState<FundingProject>();
  const [error, setError] = useState("");
  useEffect(() => { api<FundingProject>(`/funding-projects/${id}`).then(setRecord).catch((reason: Error) => setError(reason.message)); }, [id]);
  return <><Link href={`/funding-projects/${id}`}>← Funding record details</Link><h1>Edit funding record</h1>{error ? <div className="error">{error}</div> : !record ? <p role="status">Loading funding record…</p> : <><FundingEditor initial={record} category={record.category as "SPONSORED_RESEARCH" | "CONSULTANCY" | "INTERNAL_GRANT"} /><EvidenceManager entity="funding-projects" id={Number(id)} categories={evidenceTypes} /></>}</>;
}
