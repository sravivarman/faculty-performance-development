import type { Metadata } from "next";
import "./globals.css";
import '@/components/dashboard/dashboard.css';
import {DateRangeProvider} from "@/components/DateRange";
import AppHeader from "@/components/AppHeader";

export const metadata: Metadata = {
  title: "Faculty Research & Development Portal – EEE | VCE",
  description: "Research and faculty development records for Vardhaman College of Engineering.",
};
export default function RootLayout({children}: {children: React.ReactNode}) {
  return <html lang="en"><body><DateRangeProvider><AppHeader /><main>{children}</main><footer>Faculty Research &amp; Development Portal – EEE · Vardhaman College of Engineering</footer></DateRangeProvider></body></html>;
}
