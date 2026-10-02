"use client";
import {useEffect,useState} from 'react';
import {useRouter} from 'next/navigation';
import {api,INDEXING,label} from '@/lib/api';
import {useDateRange} from '@/components/DateRange';
import {DashboardReport,INDEX_DISTRIBUTION,QUARTILES} from '@/lib/publication-dashboard';
import {typeLabels} from '@/lib/dashboard-charts';
import {moduleLink} from '@/lib/research-overview';
import {DashboardSection,DashboardError} from './UI';
import {Distribution} from './Charts';
const filtersConfig={publication_type:['JOURNAL','CONFERENCE'],indexing:INDEXING,classification:['INTERNATIONAL','NATIONAL','OTHER','UNKNOWN'],quartile:['Q1','Q2','Q3','Q4','NOT_APPLICABLE','UNKNOWN']};
const titles={publication_type:'Publication Type',indexing:'Indexing',classification:'Classification',quartile:'Quartile'};
export default function PublicationAnalytics(){
  const {range,ready}=useDateRange();const router=useRouter();const [filters,setFilters]=useState<Record<string,string>>({});const [report,setReport]=useState<DashboardReport>();const [error,setError]=useState('');const [loading,setLoading]=useState(true);const [retry,setRetry]=useState(0);const query=new URLSearchParams(Object.entries({...range,...filters}).filter(([,v])=>v)).toString();
  useEffect(()=>{if(!ready)return;let active=true;setLoading(true);setReport(undefined);setError('');api<DashboardReport>(`/publication-dashboard?${query}`).then(data=>{if(active)setReport(data);}).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[query,ready,retry]);
  const select=(metric:string)=>router.push(moduleLink('publications',metric,range,filters));
  return <><h2 className="dash-section-title">Publications Analytics</h2><div className="dash-charts dash-analytics"><DashboardSection title="Publications Filter"><p>These controls refine publication analytics only. Research activity and faculty totals retain the global date range.</p><div className="dash-filters">{Object.entries(filtersConfig).map(([key,values])=><label className="field" key={key}>{titles[key as keyof typeof titles]}<select value={filters[key]||''} onChange={e=>setFilters(f=>({...f,[key]:e.target.value}))}><option value="">All</option>{values.map(v=><option key={v} value={v}>{v.startsWith('Q')?v:label(v)}</option>)}</select></label>)}</div><button className="secondary small" onClick={()=>setFilters({})}>Reset publication filters</button><p className="dash-footnote">{loading?'Loading publication analytics…':report?`${report.totals.total} matching publications · distinct records`:'Publication data unavailable.'}</p><DashboardError message={error} retry={()=>setRetry(r=>r+1)}/></DashboardSection><Distribution title="Publications by Type" labels={typeLabels} counts={report?.totals||{}} onSelect={select} loading={loading} error={error}/><Distribution title="Indexing Distribution" labels={INDEX_DISTRIBUTION} counts={report?.totals||{}} note="Indexing categories may overlap." onSelect={select} loading={loading} error={error}/><Distribution title="Quartile Distribution" labels={QUARTILES} counts={report?.totals||{}} onSelect={select} loading={loading} error={error}/></div></>;
}
