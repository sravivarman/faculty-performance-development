"use client";
import {useEffect,useRef,useState} from "react";
import type {EChartsCoreOption,EChartsType} from "echarts/core";

// Load only the chart types used by the dashboards, in the browser.
const engine=()=>import("@/lib/echarts-engine").then(module=>module.core);
const theme={color:['#2563eb','#0d9488','#8b5cf6','#ea8a23'],textStyle:{fontFamily:'Arial, sans-serif',color:'#66758b'}};
export type ChartClick={name?:string;dataIndex?:number;seriesName?:string;seriesIndex?:number};
export default function EChart({option,label,summary,height=290,loading=false,empty=false,onClick}:{option:EChartsCoreOption;label:string;summary:string;height?:number;loading?:boolean;empty?:boolean;onClick?:(event:ChartClick)=>void}){
  const element=useRef<HTMLDivElement>(null);const chart=useRef<EChartsType|null>(null);const latest=useRef(option);latest.current=option;
  const [error,setError]=useState("");const [initialized,setInitialized]=useState(false);
  const handler=useRef(onClick);handler.current=onClick;
  useEffect(()=>{let active=true;let observer:ResizeObserver|undefined;let frame=0;
    engine().then(core=>{if(!active||!element.current)return;const instance=core.init(element.current,theme,{renderer:"svg"});chart.current=instance;instance.setOption({tooltip:{renderMode:'richText',trigger:'axis'},...latest.current},{notMerge:true});instance.on('click',params=>handler.current?.(params as ChartClick));setInitialized(true);
      observer=new ResizeObserver(()=>{cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>instance.resize());});observer.observe(element.current);
    }).catch(e=>{if(active)setError((e as Error).message);});
    return()=>{active=false;observer?.disconnect();cancelAnimationFrame(frame);chart.current?.dispose();chart.current=null;};
  },[]);
  useEffect(()=>{try{chart.current?.setOption({tooltip:{renderMode:'richText',trigger:'axis'},...option},{notMerge:true});setError('');}catch(e){setError((e as Error).message);}},[option]);
  useEffect(()=>{if(initialized){if(loading)chart.current?.showLoading('default',{color:'#2563eb',text:'Loading…'});else chart.current?.hideLoading();}},[loading,initialized]);
  return <figure style={{margin:0,overflow:'hidden'}} aria-label={label}><div ref={element} role="img" aria-label={`${label}. ${summary}`} data-chart-ready={initialized} style={{width:"100%",height,minWidth:0}}/>{error&&<p role="alert">Chart unavailable: {error}</p>}{empty&&!loading&&<p role="status">No activity in the selected period.</p>}<figcaption className="sr-only">{summary}</figcaption></figure>;
}
