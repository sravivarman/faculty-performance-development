import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import '@/components/dashboard/dashboard.css';
import {DateRangeProvider} from "@/components/DateRange";
import ResearchModulesMenu from '@/components/dashboard/ResearchModulesMenu';

export const metadata: Metadata = {title: "Faculty · Research Records", description: "Department publication records and performance reporting"};
export default function RootLayout({children}: {children: React.ReactNode}) {
  return <html lang="en"><body><DateRangeProvider><header className="topbar"><Link href="/" className="brand"><span className="brand-icon">F</span> Faculty <span className="brand-muted">/ Research records</span></Link><nav><Link href="/">Overview</Link><Link href="/publications">Publications</Link><Link href="/patents">Patents</Link><Link href="/books">Books / Chapters</Link><Link href="/masters">Masters</Link><ResearchModulesMenu/></nav></header><main>{children}</main><footer>Department research · One activity, one record</footer></DateRangeProvider></body></html>;
}
