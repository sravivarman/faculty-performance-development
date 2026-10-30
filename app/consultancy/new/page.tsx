import Link from "next/link";
import FundingEditor from "@/components/FundingEditor";

export default function NewConsultancyPage() {
  return <><div className="page-heading"><div><div className="eyebrow">Consultancy</div><h1>Add consultancy project</h1><p className="muted">Record client work, agreements, financial receipts and outcomes.</p></div><Link href="/consultancy">← Back to consultancy</Link></div><FundingEditor category="CONSULTANCY" /></>;
}
