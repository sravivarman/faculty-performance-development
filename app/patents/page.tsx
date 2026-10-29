"use client";

import {useEffect,useRef,useState} from "react";
import Link from "next/link";
import DateRangeFilter,{useDateRange} from "@/components/DateRange";
import {DashboardFrame,ResearchPageHeader,KpiGrid as KpiCards,DashboardError,DashboardFilters} from "@/components/dashboard/UI";
import {Distribution,SeriesChart} from "@/components/dashboard/Charts";
import FacultyContributionTable from "@/components/dashboard/FacultyContributionTable";
import PaginationControls,{RecordPageSize} from "@/components/PaginationControls";
import type {TrendPoint} from "@/lib/dashboard-charts";
import PatentTypeSelect from "@/components/PatentTypeSelect";
import {PATENT_TYPES} from "@/lib/patents";
import PatentTable from "@/components/PatentTable";
import {api,label,Masters,paginatedResult} from "@/lib/api";
import {Patent,patentMetrics,PatentPersonKpi,STATUSES} from "@/lib/patents";

type PageResult={items:Patent[];total:number;page:number;page_size:number|"all"};
const pageSizeFrom=(value:string|null):RecordPageSize=>value==="all"?"all":[10,25,50].includes(Number(value))?Number(value) as 10|25|50:25;

export default function PatentDashboard(){
  const {range,ready}=useDateRange();
  const [filters,setFilters]=useState<Record<string,string>>({});
  const [drill,setDrill]=useState<Record<string,string>>({metric:"unique"});
  const [masters,setMasters]=useState<Masters>();
  const [options,setOptions]=useState<{offices:string[];countries:string[];current_department:string}>();
  const [counts,setCounts]=useState<Record<string,number>>({});
  const [result,setResult]=useState<PageResult>({items:[],total:0,page:1,page_size:25});
  const [faculty,setFaculty]=useState<PatentPersonKpi[]>([]);
  const [students,setStudents]=useState<PatentPersonKpi[]>([]);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(true);
  const [initialized,setInitialized]=useState(false);
  const [types,setTypes]=useState<Record<string,number>>({});
  const [trend,setTrend]=useState<TrendPoint[]>([]);
  const [chartError,setChartError]=useState("");
  const [listLoading,setListLoading]=useState(true);
  const [page,setPage]=useState(1);
  const [pageSize,setPageSize]=useState<RecordPageSize>(25);
  const previousRange=useRef("");

  useEffect(()=>{
    Promise.all([api<Masters>("/masters"),api<{offices:string[];countries:string[];current_department:string}>("/patent-options")]).then(([m,o])=>{setMasters(m);setOptions(o);}).catch(e=>setError(e.message));
    const params=new URLSearchParams(window.location.search);
    setFilters(Object.fromEntries(["patent_type","current_status","faculty_id","student_participation","patent_office","country","include_inactive"].map(k=>[k,params.get(k)||""])));
    setDrill({metric:params.get("metric")||"unique",drill_faculty_id:params.get("drill_faculty_id")||"",drill_student_id:params.get("drill_student_id")||"",list_from_date:params.get("list_from_date")||"",list_to_date:params.get("list_to_date")||""});
    setPage(Math.max(1,Number(params.get("page"))||1));setPageSize(pageSizeFrom(params.get("page_size")));setInitialized(true);
  },[]);
  const dashboardQuery=new URLSearchParams(Object.entries({...filters,...range}).filter(([,v])=>v)).toString();
  const listQuery=new URLSearchParams(Object.entries({...filters,...range,...drill,page:String(page),page_size:String(pageSize),...(drill.list_from_date?{from_date:drill.list_from_date,to_date:drill.list_to_date}:{})}).filter(([k,v])=>v&&!k.startsWith("list_"))).toString();
  const reportQuery=new URLSearchParams(Object.entries({...filters,...range,...drill,page:String(page),page_size:String(pageSize)}).filter(([,v])=>v)).toString();
  const exportQuery=new URLSearchParams(Object.entries({...filters,...range,...drill,...(drill.list_from_date?{from_date:drill.list_from_date,to_date:drill.list_to_date}:{})}).filter(([k,v])=>v&&!k.startsWith("list_"))).toString();
  useEffect(()=>{if(!ready||!initialized)return;let active=true;setLoading(true);setChartError("");api<{totals:Record<string,number>;faculty:PatentPersonKpi[];trend:TrendPoint[];types:Record<string,number>}>(`/patent-dashboard?${dashboardQuery}`).then(data=>{if(active){setCounts(data.totals);setFaculty(data.faculty);setTrend(data.trend);setTypes(data.types);}}).catch(e=>{if(active){setCounts({});setFaculty([]);setTrend([]);setTypes({});setChartError(e.message);}}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[dashboardQuery,ready,initialized]);
  useEffect(()=>{if(!ready||!initialized)return;let active=true;setListLoading(true);setError("");api<unknown>(`/patents?${listQuery}`).then(data=>{if(active)setResult(paginatedResult<Patent>(data,"Patents"));}).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setListLoading(false);});return()=>{active=false;};},[listQuery,ready,initialized]);
  useEffect(()=>{if(!ready||!initialized)return;let active=true;api<PatentPersonKpi[]>(`/patent-kpis/students?${dashboardQuery}`).then(data=>{if(active)setStudents(data);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[dashboardQuery,ready,initialized]);
  useEffect(()=>{if(ready&&initialized&&window.location.pathname==="/patents")window.history.replaceState(window.history.state,"",`/patents?${reportQuery}`);},[reportQuery,ready,initialized]);
  useEffect(()=>{if(!ready)return;const key=`${range.from_date}/${range.to_date}`;if(previousRange.current&&previousRange.current!==key){setDrill(d=>({...d,list_from_date:"",list_to_date:""}));setPage(1);}previousRange.current=key;},[range,ready]);
  function filter(key:string,value:string){setFilters({...filters,[key]:value});setDrill({metric:"unique"});setPage(1);}
  function resetFilters(){setFilters({});setDrill({metric:"unique"});setPage(1);}
  function select(values:Record<string,string>){if(values.metric==="filed"&&values.list_from_date)values={...values,metric:"filed_event"};setDrill(values);setPage(1);document.getElementById("patent-records")?.scrollIntoView({behavior:"smooth"});}
  const peopleTable=(rows:PatentPersonKpi[],kind:"faculty"|"student")=><div className="table-wrap"><table><thead><tr><th>{kind==="faculty"?"Faculty":"Student / Roll number"}</th>{(kind==="faculty"?["claimed","invented","filed","published","granted"]:["invented","filed","published","granted"]).map(k=><th key={k}>{k==="invented"&&kind==="student"?"Involved":label(k)}</th>)}</tr></thead><tbody>{rows.map(p=><tr key={p.id}><td>{p.name}{p.roll_number&&<small>{p.roll_number}</small>}{p.faculty_collaborators&&<small>Faculty: {p.faculty_collaborators.map(f=>f.name).join(", ")||"—"}</small>}</td>{(kind==="faculty"?["claimed","invented","filed","published","granted"]:["invented","filed","published","granted"]).map(k=><td key={k}><button className="link-button" onClick={()=>select({[kind==="faculty"?"drill_faculty_id":"drill_student_id"]:String(p.id),metric:k==="invented"?"unique":k})}>{p[k as "claimed"|"invented"|"filed"|"published"|"granted"]}</button></td>)}</tr>)}</tbody></table></div>;
  return <DashboardFrame><ResearchPageHeader title="Patents Overview" subtitle="One patent throughout its lifecycle. Every inventor and collaboration retained."><Link href="/patents/records">All patent records</Link><a className="button secondary" href={`/api/patent-export?${exportQuery}`}>Export CSV</a><Link className="button" href="/patents/new">+ Add patent</Link></ResearchPageHeader><DateRangeFilter/>{error&&<div className="error" role="alert">{error}</div>}
    <DashboardFilters><PatentTypeSelect filter value={filters.patent_type||""} onChange={value=>filter("patent_type",value)}/><label className="field">Current status<select value={filters.current_status||""} onChange={e=>filter("current_status",e.target.value)}><option value="">All statuses</option>{STATUSES.map(s=><option key={s}>{s}</option>)}</select></label><label className="field">Faculty inventor<select value={filters.faculty_id||""} onChange={e=>filter("faculty_id",e.target.value)}><option value="">All Faculty</option>{masters?.faculty.map(f=><option key={f.id} value={f.id}>{f.name}{f.is_active?"":" (historical)"}</option>)}</select></label><label className="field">Student participation<select value={filters.student_participation||""} onChange={e=>filter("student_participation",e.target.value)}><option value="">All patents</option><option value="true">With current-department students</option><option value="false">Without current-department students</option></select></label><label className="field">Patent office<select value={filters.patent_office||""} onChange={e=>filter("patent_office",e.target.value)}><option value="">All offices</option>{options?.offices.map(o=><option key={o}>{o}</option>)}</select></label><label className="field">Country<select value={filters.country||""} onChange={e=>filter("country",e.target.value)}><option value="">All countries</option>{options?.countries.map(c=><option key={c}>{c}</option>)}</select></label><label className="check"><input type="checkbox" checked={filters.include_inactive==="true"} onChange={e=>filter("include_inactive",e.target.checked?"true":"")}/>Include inactive records</label><button type="button" className="secondary" onClick={resetFilters}>Reset filters</button></DashboardFilters>
    <h2>Department patents</h2><KpiCards labels={Object.fromEntries(Object.entries(patentMetrics).filter(([key])=>key!=="unique_students"))} counts={counts} loading={loading} active={drill.metric} onSelect={metric=>select({metric})}/><p className="muted">Unique patents, participation and collaboration count each patent once when any recorded lifecycle event falls in the selected range. Filed includes patents with current status FILED and a filing date in range. Published and Granted use their respective event dates. Only patents with a current-department inventor contribute.</p><DashboardError message={chartError}/><div className="dash-charts"><Distribution title="Patents by Type" labels={PATENT_TYPES} counts={types} onSelect={value=>filter("patent_type",value)} loading={loading} error={chartError}/><SeriesChart title="Patent Lifecycle Trend" rows={trend} series={{filed:"Filed",published:"Published",granted:"Granted"}} loading={loading} error={chartError} note="Lifecycle trends count dated filing, publication, and grant events, regardless of current status." onSelect={(row,key)=>select({metric:key==="filed"?"filed_event":key,list_from_date:String(row.from_date),list_to_date:String(row.to_date)})}/><Distribution title="Filed / Published / Granted" labels={{filed:"Filed",published:"Published",granted:"Granted"}} counts={counts} onSelect={metric=>select({metric})} loading={loading} error={chartError}/><Distribution title="Collaboration Distribution" labels={{with_students:"With Students",interdepartmental:"Interdepartmental",external_collaboration:"External Collaboration"}} counts={counts} onSelect={metric=>select({metric})} note="Collaboration categories may overlap. Counts use recorded lifecycle events in the selected range." loading={loading} error={chartError}/><Distribution title="Patent Activity by Faculty" labels={Object.fromEntries(faculty.map(f=>[String(f.id),f.name]))} counts={Object.fromEntries(faculty.map(f=>[String(f.id),f.invented]))} onSelect={id=>select({metric:"unique",drill_faculty_id:id})} loading={loading} error={chartError}/></div>
    <section className="panel" id="patent-records"><div className="row-between"><h2>{drill.metric==="filed_event"?"Filed events":patentMetrics[drill.metric as keyof typeof patentMetrics]||label(drill.metric)} · {result.total} records</h2><button className="secondary small" onClick={()=>{setDrill({metric:"unique"});setPage(1);}}>Reset drill-down</button></div>{["unique_faculty","unique_students"].includes(drill.metric)&&<p className="muted">The KPI counts distinct people; this list shows their patents.</p>}<p className="dash-footnote">{drill.list_from_date||range.from_date} to {drill.list_to_date||range.to_date}</p>{listLoading?<p role="status">Loading patent records...</p>:<PatentTable patents={result.items}/>}<PaginationControls page={result.page} pageSize={pageSize} total={result.total} loading={listLoading} onPageChange={setPage} onPageSizeChange={next=>{setPageSize(next);setPage(1);}}/></section>
    <FacultyContributionTable title="Faculty patent contributions" columns={{claimed:"Claimed Patents",invented:"Inventor Patents",filed:"Filed",published:"Published",granted:"Granted"}} rows={faculty.map(({id,name,claimed,invented,filed,published,granted})=>({id,name,claimed,invented,filed,published,granted}))} loading={loading} error={chartError} note="Claimed and inventor counts use any recorded lifecycle event in the selected range. Filed counts patents still in FILED status; Published and Granted count their dated milestones." onSelect={(row,key)=>select({drill_faculty_id:String(row.id),metric:key==="invented"?"unique":key})}/><section className="panel"><h2>Student patent involvement</h2><KpiCards labels={{unique_students:"Student Inventors"}} counts={counts} loading={loading} onSelect={metric=>select({metric})}/>{peopleTable(students,"student")}</section></DashboardFrame>;
}
