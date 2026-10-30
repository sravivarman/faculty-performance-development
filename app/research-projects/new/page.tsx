import Link from "next/link";
import FundingEditor from "@/components/FundingEditor";

export default function NewResearchProjectPage() {
  return <><div className="page-heading"><div><div className="eyebrow">Sponsored research</div><h1>Add research project</h1><p className="muted">Create a proposal or sanctioned-project record with its PI and Co-PIs.</p></div><Link href="/research-projects">← Back to projects</Link></div><FundingEditor category="SPONSORED_RESEARCH" /></>;
}
