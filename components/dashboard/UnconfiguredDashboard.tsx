"use client";
import DateRangeFilter from '@/components/DateRange';
import {DashboardFrame,ResearchPageHeader,KpiGrid,DashboardSection,EmptyState} from './UI';
import FacultyContributionTable from './FacultyContributionTable';
const config={
  fdp:{title:'FDP / Workshop / Seminar Overview',labels:{total:'Total Activities',attended:'Attended',conducted:'Conducted',fdp:'FDP',workshop:'Workshop',seminar:'Seminar',contributors:'Faculty Contributors'},charts:['Activity Type Distribution','Attended vs Conducted','Activity Trend']},
  certifications:{title:'Certifications Overview',labels:{total:'Total Certifications',faculty:'Faculty Certified',nptel:'NPTEL',industry:'Industry Certifications',other:'Other'},charts:['Certification Trend','Certification Type Distribution']},
  proposals:{title:'Research Proposals Overview',labels:{submitted:'Submitted',sanctioned:'Sanctioned',rejected:'Rejected / Not Sanctioned',pending:'Pending',funds:'Funds Sanctioned',contributors:'Faculty Contributors'},charts:['Submitted vs Sanctioned Trend','Proposal Status','Funding Trend']},
  consultancy:{title:'Consultancy Overview',labels:{total:'Consultancy Projects',active:'Active',completed:'Completed',revenue:'Revenue Generated',contributors:'Faculty Contributors'},charts:['Consultancy Trend','Revenue Trend','Project Status']},
} as const;
export default function UnconfiguredDashboard({module}:{module:keyof typeof config}){const data=config[module];return <DashboardFrame><ResearchPageHeader title={data.title} subtitle="Department research activity and faculty contribution"/><DateRangeFilter/><EmptyState detail="This module has no reporting backend yet. Counts, financial amounts and records are unavailable."/><KpiGrid labels={data.labels} counts={Object.fromEntries(Object.keys(data.labels).map(key=>[key,null]))} financial={['funds','revenue']}/><div className="dash-charts">{data.charts.map(title=><DashboardSection title={title} key={title}><EmptyState/></DashboardSection>)}</div><FacultyContributionTable columns={{activity:'Activities'}} rows={[]} note="Not configured. Faculty contribution data will appear when this module is available."/></DashboardFrame>;}
