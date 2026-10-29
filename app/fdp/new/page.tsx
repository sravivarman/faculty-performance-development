import Link from "next/link";
import FdpEditor from "@/components/FdpEditor";

export default function NewFdpActivity() {
  return <><div className="page-heading"><div><div className="eyebrow">Faculty development activity</div><h1>Add activity</h1><p className="muted">Record the activity, Faculty participation and resource persons once.</p></div><Link href="/fdp">← Back to activities</Link></div><FdpEditor /></>;
}
