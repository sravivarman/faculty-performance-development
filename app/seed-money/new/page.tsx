import Link from "next/link";
import FundingEditor from "@/components/FundingEditor";

export default function NewSeedMoneyPage() {
  return <><div className="page-heading"><div><div className="eyebrow">Seed money / internal grant</div><h1>Add internal grant</h1><p className="muted">Record sanctioned support, beneficiaries, utilization and outcomes.</p></div><Link href="/seed-money">← Back to internal grants</Link></div><FundingEditor category="INTERNAL_GRANT" /></>;
}
