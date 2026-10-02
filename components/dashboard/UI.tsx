"use client";
import type {ReactNode} from 'react';
import {Card} from './Card';
import {FacultyDetailsProvider} from './FacultyResearchDetails';
import {currency} from '@/lib/research-overview';

export function DashboardFrame({children}:{children:ReactNode}){return <FacultyDetailsProvider><div className="research-dashboard">{children}</div></FacultyDetailsProvider>;}
export function ResearchPageHeader({title,subtitle,children}:{title:string;subtitle:string;children?:ReactNode}){return <div className="dash-heading"><div><span className="dash-kicker">Department research records</span><h1>{title}</h1><p>{subtitle}</p></div><div className="actions">{children}</div></div>;}
export function DashboardSection({title,children,note,id}:{title:string;children:ReactNode;note?:string;id?:string}){return <Card asChild className="dash-chart dash-section"><section id={id}><h2>{title}</h2>{note&&<p>{note}</p>}{children}</section></Card>;}
export const DashboardTile=DashboardSection;
export function EmptyState({message='Not configured',detail}:{message?:string;detail?:string}){return <div className="dash-empty" role="status"><strong>{message}</strong>{detail&&<p>{detail}</p>}</div>;}
export function DashboardError({message,retry}:{message?:string;retry?:()=>void}){return message?<div className="error" role="alert">{message}{retry&&<button className="secondary small" onClick={retry}>Retry</button>}</div>:null;}
export function KpiGrid({labels,counts,loading,onSelect,active,financial=[],allowUnavailable=false}:{labels:Record<string,string>;counts:Record<string,number|null|undefined>;loading?:boolean;onSelect?:(key:string)=>void;active?:string;financial?:string[];allowUnavailable?:boolean}){
  return <div className="dash-grid">{Object.entries(labels).map(([key,title])=>{const value=counts[key];const unavailable=value===null;const text=loading?'Loading':unavailable?'Not configured':value===undefined?'Unavailable':financial.includes(key)?currency(value):String(value);return <Card asChild key={key} className={`dash-card ${unavailable?'dash-inactive':'dash-available'} ${key===active?'dash-active':''}`}><button type="button" disabled={loading||!onSelect||value===undefined||(unavailable&&!allowUnavailable)} aria-label={`${title}: ${text}`} onClick={()=>onSelect?.(key)}><span className="dash-card-label">{title}</span><strong className="dash-number">{loading?'—':text}</strong><small>{unavailable?'Module or field not yet configured':onSelect?'Explore records ↗':'Selected inclusive period'}</small></button></Card>;})}</div>;
}
export function DashboardFilters({children}:{children:ReactNode}){return <Card className="dash-chart dash-filters" aria-label="Report filters">{children}</Card>;}
export function NeedsAttentionPanel({labels,counts,onSelect,loading}:{labels:Record<string,string>;counts:Record<string,number>;onSelect:(key:string)=>void;loading?:boolean}){return <DashboardSection title="Needs Attention" note="Data completeness indicators, separate from performance."><KpiGrid labels={labels} counts={counts} onSelect={onSelect} loading={loading}/></DashboardSection>;}
