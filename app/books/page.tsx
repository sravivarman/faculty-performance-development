"use client";
import {useEffect,useRef,useState} from "react";
import Link from "next/link";
import DateRangeFilter,{useDateRange} from "@/components/DateRange";
import {DashboardFrame,ResearchPageHeader,KpiGrid as KpiCards,DashboardSection,EmptyState,DashboardError,DashboardFilters} from "@/components/dashboard/UI";
import {Distribution,SeriesChart} from "@/components/dashboard/Charts";
import FacultyContributionTable from "@/components/dashboard/FacultyContributionTable";
import type {TrendPoint} from "@/lib/dashboard-charts";
import BookTable from "@/components/BookTable";
import {api,label,Masters} from "@/lib/api";
import {Book,bookMetrics,BookPersonKpi} from "@/lib/books";

export default function BooksDashboard(){
  const {range,ready}=useDateRange();
  const [filters,setFilters]=useState<Record<string,string>>({});const [drill,setDrill]=useState<Record<string,string>>({metric:"total"});
  const [masters,setMasters]=useState<Masters>();const [options,setOptions]=useState<{publishers:string[];current_department:string}>();
  const [classification,setClassification]=useState<Record<string,number>>({});
  const [counts,setCounts]=useState<Record<string,number|null>>({});const [books,setBooks]=useState<Book[]>([]);
  const [faculty,setFaculty]=useState<BookPersonKpi[]>([]);const [students,setStudents]=useState<BookPersonKpi[]>([]);
  const [error,setError]=useState("");const [loading,setLoading]=useState(true);
  const [initialized,setInitialized]=useState(false);const previousRange=useRef("");
  const [trend,setTrend]=useState<TrendPoint[]>([]);const [chartError,setChartError]=useState("");const [listLoading,setListLoading]=useState(true);
  useEffect(()=>{
    Promise.all([api<Masters>("/masters"),api<{publishers:string[];current_department:string}>("/book-options")]).then(([m,o])=>{setMasters(m);setOptions(o);}).catch(e=>setError(e.message));
    const params=new URLSearchParams(window.location.search);
    setFilters(Object.fromEntries(["work_type","faculty_id","student_participation","interdepartmental","external_collaboration","publisher","isbn_search","include_inactive"].map(k=>[k,params.get(k)||""])));
    setDrill({metric:params.get("metric")||"total",drill_faculty_id:params.get("drill_faculty_id")||"",drill_student_id:params.get("drill_student_id")||"",list_from_date:params.get("list_from_date")||"",list_to_date:params.get("list_to_date")||""});
    setInitialized(true);
  },[]);
  const query=new URLSearchParams(Object.entries({...filters,...range}).filter(([,v])=>v)).toString();
  const detailQuery=new URLSearchParams(Object.entries({...filters,...range,...drill,...(drill.list_from_date?{from_date:drill.list_from_date,to_date:drill.list_to_date}:{})}).filter(([k,v])=>v&&!k.startsWith("list_"))).toString();
  useEffect(()=>{if(!ready||!initialized)return;let active=true;setLoading(true);setChartError("");api<{totals:Record<string,number|null>;faculty:BookPersonKpi[];trend:TrendPoint[];classification:Record<string,number>}>(`/book-dashboard?${query}`).then(k=>{if(active){setCounts(k.totals);setClassification(k.classification);setFaculty(k.faculty);setTrend(k.trend);}}).catch(e=>{if(active){setCounts({});setFaculty([]);setTrend([]);setChartError(e.message);}}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[query,ready,initialized]);
  useEffect(()=>{if(!ready||!initialized)return;let active=true;setListLoading(true);setError("");api<Book[]>(`/books?${detailQuery}`).then(b=>{if(active)setBooks(b);}).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setListLoading(false);});return()=>{active=false;};},[detailQuery,ready,initialized]);
  useEffect(()=>{if(!ready||!initialized)return;let active=true;api<BookPersonKpi[]>(`/book-kpis/students?${query}`).then(s=>{if(active)setStudents(s);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[query,ready,initialized]);
  const reportQuery=new URLSearchParams(Object.entries({...filters,...range,...drill}).filter(([,v])=>v)).toString();
  useEffect(()=>{if(ready&&initialized&&window.location.pathname==="/books")window.history.replaceState(window.history.state,"",`/books?${reportQuery}`);},[reportQuery,ready,initialized]);
  useEffect(()=>{if(!ready)return;const key=`${range.from_date}/${range.to_date}`;if(previousRange.current&&previousRange.current!==key)setDrill(d=>({...d,list_from_date:"",list_to_date:""}));previousRange.current=key;},[range,ready]);
  function filter(key:string,value:string){setFilters({...filters,[key]:value});setDrill({metric:"total"});}
  function select(values:Record<string,string>){setDrill(values);document.getElementById("book-records")?.scrollIntoView({behavior:"smooth"});}
  function peopleTable(rows:BookPersonKpi[],kind:"faculty"|"student"){
    const keys=kind==="faculty"?["books_claimed","books_authored","chapters_claimed","chapters_authored","claimed","authored"]:["books_authored","chapters_authored","authored"];
    return <div className="table-wrap"><table><thead><tr><th>{kind==="faculty"?"Faculty":"Student / Roll number"}</th>{keys.map(k=><th key={k}>{k==="authored"?(kind==="faculty"?"Total Authored":"Total Works"):k==="claimed"?"Total Claimed":label(k)}</th>)}{kind==="student"&&<th>Faculty Collaborators</th>}</tr></thead><tbody>{rows.map(p=><tr key={p.id}><td>{p.name}<small>{p.roll_number}</small></td>{keys.map(k=><td key={k}><button className="link-button" onClick={()=>select({[kind==="faculty"?"drill_faculty_id":"drill_student_id"]:String(p.id),metric:k})}>{p[k as keyof BookPersonKpi] as number}</button></td>)}{kind==="student"&&<td>{p.faculty_collaborators?.map(f=>f.name).join(", ")||"—"}</td>}</tr>)}</tbody></table></div>;
  }
  return <DashboardFrame><ResearchPageHeader title="Books / Chapters Overview" subtitle="One work, one department count. Every author, editor and collaboration retained."><Link href="/books/records">All work records</Link><Link className="button" href="/books/new">+ Add Book / Book Chapter</Link></ResearchPageHeader>
    <DateRangeFilter/>{error&&<div className="error" role="alert">{error}</div>}
    <DashboardFilters><label className="field">Work Type<select value={filters.work_type||""} onChange={e=>filter("work_type",e.target.value)}><option value="">Books + Chapters</option><option value="BOOK">Book</option><option value="BOOK_CHAPTER">Book Chapter</option></select></label><label className="field">Faculty<select value={filters.faculty_id||""} onChange={e=>filter("faculty_id",e.target.value)}><option value="">All faculty</option>{masters?.faculty.map(f=><option key={f.id} value={f.id}>{f.name}</option>)}</select></label>
    {(["student_participation","interdepartmental","external_collaboration"] as const).map(k=><label className="field" key={k}>{label(k)}<select value={filters[k]||""} onChange={e=>filter(k,e.target.value)}><option value="">All works</option><option value="true">With {label(k).toLowerCase()}</option><option value="false">Without {label(k).toLowerCase()}</option></select></label>)}
    <label className="field">Publisher<select value={filters.publisher||""} onChange={e=>filter("publisher",e.target.value)}><option value="">All publishers</option>{options?.publishers.map(p=><option key={p}>{p}</option>)}</select></label><label className="field">ISBN search<input value={filters.isbn_search||""} onChange={e=>filter("isbn_search",e.target.value)}/></label><label className="check"><input type="checkbox" checked={filters.include_inactive==="true"} onChange={e=>filter("include_inactive",e.target.checked?"true":"")}/>Include inactive records</label></DashboardFilters>
    <KpiCards labels={{total:"Total Works",books:"Books",chapters:"Book Chapters",international:"International",national:"National",with_students:"Student-involved",faculty_contributors:"Faculty Contributors"}} counts={counts} loading={loading} active={drill.metric} onSelect={metric=>{select({metric});}}/><p className="muted">Publication date is used for every count, with both boundaries included. Chapters require a current-department chapter author; parent-book editors alone do not qualify. Author counts exclude editors.</p>
    <details className="dash-additional"><summary>Collaboration and authorship indicators</summary><KpiCards labels={{interdepartmental:bookMetrics.interdepartmental,external_collaboration:bookMetrics.external_collaboration,unique_faculty:bookMetrics.unique_faculty,unique_students:bookMetrics.unique_students}} counts={counts} loading={loading} onSelect={metric=>select({metric})}/></details>
    <DashboardError message={chartError}/><div className="dash-charts"><Distribution title="Books vs Chapters" labels={{books:"Books",chapters:"Book Chapters"}} counts={{books:counts.books||0,chapters:counts.chapters||0}} onSelect={metric=>select({metric})} loading={loading} error={chartError}/><SeriesChart title="Books / Chapters Trend" rows={trend} series={{books:"Books",chapters:"Book Chapters"}} loading={loading} error={chartError} onSelect={(row,key)=>select({metric:key,list_from_date:String(row.from_date),list_to_date:String(row.to_date)})}/><Distribution title="Classification Distribution" labels={{international:"International",national:"National",other:"Other",unknown:"Unknown"}} counts={classification} loading={loading} error={chartError} onSelect={metric=>select({metric})} note="Historical records without classification remain Unknown."/></div>
    <section className="panel" id="book-records"><div className="row-between"><h2>{bookMetrics[drill.metric as keyof typeof bookMetrics]||label(drill.metric)} · {loading?"Loading…":`${books.length} records`}</h2><button className="secondary small" onClick={()=>setDrill({metric:"total"})}>Reset drill-down</button></div>{["unique_faculty","unique_students","faculty_contributors"].includes(drill.metric)&&<p className="muted">The KPI counts distinct authors; this list shows the works involving those authors.</p>}<p className="dash-footnote">{drill.list_from_date||range.from_date} to {drill.list_to_date||range.to_date}</p>{listLoading?<p role="status">Loading book records...</p>:<BookTable books={books} query={reportQuery}/> }</section>
    <FacultyContributionTable title="Faculty contributions" columns={{books_claimed:"Books Claimed",books_authored:"Books Authored",chapters_claimed:"Chapters Claimed",chapters_authored:"Chapters Authored",claimed:"Total Claimed",authored:"Total Authored",participated:"Total Works"}} rows={faculty.map(({id,name,books_claimed,books_authored,chapters_claimed,chapters_authored,claimed,authored,participated})=>({id,name,books_claimed,books_authored,chapters_claimed,chapters_authored,claimed,authored,participated}))} loading={loading} error={chartError} note="Claims and authored works remain separate; eligible editors appear in the faculty profile." onSelect={(row,key)=>select({drill_faculty_id:String(row.id),metric:key})}/><section className="panel"><h2>Student authorship</h2>{peopleTable(students,"student")}</section>
  </DashboardFrame>;
}
