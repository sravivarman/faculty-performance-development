import Link from "next/link";
import CertificationEditor from "@/components/CertificationEditor";

export default function NewCertification() {
  return <><div className="page-heading"><div><div className="eyebrow">Certification / MOOC record</div><h1>Add certification</h1><p className="muted">Record completed outcomes or current learning work.</p></div><Link href="/certifications">← Back to certifications</Link></div><CertificationEditor /></>;
}
