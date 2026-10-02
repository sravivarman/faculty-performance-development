"use client";
import {useEffect,useState} from 'react';
import Link from 'next/link';
import {useRouter} from 'next/navigation';
import DateRangeFilter,{useDateRange} from '@/components/DateRange';
import {api} from '@/lib/api';
import {ResearchOverview,moduleLink} from '@/lib/research-overview';
import {DashboardFrame,ResearchPageHeader,KpiGrid,DashboardError} from '@/components/dashboard/UI';
import {ResearchActivityTrend,Distribution} from '@/components/dashboard/Charts';
import PublicationAnalytics from '@/components/dashboard/PublicationAnalytics';
import {PATENT_TYPES} from "@/lib/patents";
import FacultyContributionTable from '@/components/dashboard/FacultyContributionTable';
const activities={journal:'Journals',conference:'Conferences',patents:'Patents',books:'Books / Chapters',fdp:'FDP / Workshop / Seminar',certifications:'Certifications',proposals:'Research Proposals',consultancy:'Consultancy'};
const columns={journal:'Journals',conference:'Conferences',publications_claimed:'Publications Claimed',publications_authored:'Publications Authored',patents_invented:'Patents',books:'Books / Chapters',fdp:'FDP / Workshop / Seminar',certifications:'Certifications',proposals:'Research Proposals',consultancy:'Consultancy'};
type Overview=Omit<ResearchOverview,'faculty_summary'>&{patent_types:Record<string,number>;faculty_summary:({id:number;name:string}&Record<keyof typeof columns,number|null>)[]};
export default function ResearchDashboard(){
  const {range,ready}=useDateRange();const router=useRouter();const [report,setReport]=useState<Overview>();const [error,setError]=useState('');const [loading,setLoading]=useState(true);const [retry,setRetry]=useState(0);const query=new URLSearchParams(range).toString();
  useEffect(()=>{if(!ready)return;let active=true;setLoading(true);setError('');api<Overview>(`/research/overview?${query}`).then(data=>{if(active)setReport(data);}).catch(e=>{if(active){setReport(undefined);setError(e.message);}}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[query,ready,retry]);
  function navigate(key:string,extra:Record<string,string>={}){const module=key==='journal'||key==='conference'||key.startsWith('publications_')?'publications':key.startsWith('patents')?'patents':key;const metric=key==='journal'||key==='conference'?key:key==='patents'||key==='patents_invented'?'unique':key.endsWith('claimed')?'claimed':key==='books'&&extra.drill_faculty_id?'participated':'total';router.push(moduleLink(module,metric,range,extra));}
  return <DashboardFrame><ResearchPageHeader title="Research Overview" subtitle="Department research performance and activity"><Link className="button" href="/publications/new">+ Add publication</Link></ResearchPageHeader><DateRangeFilter/><DashboardError message={error} retry={()=>setRetry(r=>r+1)}/><h2>Research Activity</h2><KpiGrid allowUnavailable labels={activities} counts={{...report?.activity_totals,journal:report?.outcomes.journal,conference:report?.outcomes.conference}} loading={loading} onSelect={navigate}/><ResearchActivityTrend/><Distribution title="Patents by Type" labels={PATENT_TYPES} counts={report?.patent_types||{}} loading={loading} error={error} onSelect={patent_type=>navigate("patents",{patent_type})}/><PublicationAnalytics/><FacultyContributionTable columns={columns} rows={report?.faculty_summary||[]} loading={loading} error={error} note="Unique authored Journal and Conference records. Claims and authorship remain separate. Patents count once for any recorded lifecycle event in the selected range; books include eligible authors and editors." onSelect={(row,key)=>navigate(key,{drill_faculty_id:String(row.id)})}/></DashboardFrame>;
}
