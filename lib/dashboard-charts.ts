import type {EChartsCoreOption} from "echarts/core";
import type {ResearchOverview} from "./research-overview";
import {INDEX_DISTRIBUTION,QUARTILES} from "./publication-dashboard";

const colors=["#2563eb","#0d9488","#8b5cf6"];
export type TrendPoint={month:string;from_date:string;to_date:string;[key:string]:string|number};
const base={animation:false,textStyle:{fontFamily:"Arial, sans-serif",color:"#66758b"},aria:{enabled:true},tooltip:{trigger:"axis",renderMode:"richText"}};
export type ActivityTrend={available_years:number[];calendar_year:number;granularity:string;series:Record<string,string>;unavailable_modules:Record<string,string>;buckets:({label:string}&Record<string,string|number|null>)[]};
export function activityTrendOption(trend:ActivityTrend):EChartsCoreOption{
  const option=trendOption([]);
  return {...option,color:["#2563eb","#0d9488","#8b5cf6","#ea8a23"],legend:{...option.legend as object,type:"scroll"},xAxis:{...option.xAxis as object,data:trend.buckets.map(b=>b.label)},series:Object.entries(trend.series).filter(([key])=>!(key in trend.unavailable_modules)).map(([key,name])=>({name,type:"line",symbolSize:6,lineStyle:{width:2.5},data:trend.buckets.map(b=>b[key])}))};
}
export function trendOption(trend:ResearchOverview['trend']):EChartsCoreOption{
  return {...base,color:colors,legend:{bottom:0,icon:"roundRect",itemWidth:12,itemHeight:7,textStyle:{color:"#66758b",fontSize:11}},grid:{left:42,right:18,top:25,bottom:55},xAxis:{type:"category",boundaryGap:false,data:trend.map(m=>m.month),axisTick:{show:false},axisLine:{lineStyle:{color:"#e2e8f0"}},axisLabel:{fontSize:10}},yAxis:{type:"value",minInterval:1,splitLine:{lineStyle:{color:"#edf1f7",type:"dashed"}}},series:([['publications','Publications'],['patents','Patents Filed'],['books','Books / Chapters']] as const).map(([key,name])=>({name,type:"line",smooth:false,symbolSize:6,lineStyle:{width:2.5},data:trend.map(m=>m[key])}))};
}
export function distributionOption(labels:Record<string,string>,counts:Record<string,number>,color=colors[0]):EChartsCoreOption{
  return {...base,grid:{left:108,right:35,top:12,bottom:28},xAxis:{type:"value",minInterval:1,splitLine:{lineStyle:{color:"#edf1f7",type:"dashed"}}},yAxis:{type:"category",inverse:true,data:Object.values(labels),axisTick:{show:false},axisLine:{show:false},axisLabel:{fontSize:11}},series:[{type:"bar",barMaxWidth:19,itemStyle:{color,borderRadius:[0,4,4,0]},label:{show:true,position:"right",color:"#526078",fontSize:11},data:Object.keys(labels).map(key=>counts[key]||0)}]};
}
export function lineOption(rows:{month:string;[key:string]:string|number}[],series:Record<string,string>):EChartsCoreOption{
  const template=trendOption([]);
  return {...template,xAxis:{...template.xAxis as object,data:rows.map(row=>row.month)},series:Object.entries(series).map(([key,name])=>({name,type:'line',symbolSize:6,lineStyle:{width:2.5},data:rows.map(row=>Number(row[key])||0)}))};
}
export const typeLabels={journal:"Journal",conference:"Conference"};
export {INDEX_DISTRIBUTION,QUARTILES};
export const summary=(labels:Record<string,string>,counts:Record<string,number>)=>Object.entries(labels).map(([key,name])=>`${name}: ${counts[key]||0}`).join("; ");
