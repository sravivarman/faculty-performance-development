/** Presets resolve to inclusive ISO dates; reporting APIs receive only these dates. */
export type DateRange = {from_date:string;to_date:string};
export const DATE_PRESETS = ["Custom","This Calendar Year","Last Calendar Year","This Academic Year","Last Academic Year","This Month","Last Month"] as const;
export const EXTRA_DATE_PRESETS = ["This Quarter","Previous Quarter","This Half-Year","Previous Half-Year"] as const;
export type DatePreset = typeof DATE_PRESETS[number] | typeof EXTRA_DATE_PRESETS[number];
export const isDatePreset = (value:unknown):value is DatePreset => [...DATE_PRESETS,...EXTRA_DATE_PRESETS].some(preset=>preset===value);
const iso=(date:Date)=>`${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}-${String(date.getDate()).padStart(2,"0")}`;

export function presetRange(preset:string,today=new Date()):DateRange {
  if(Number.isNaN(today.getTime())) throw new RangeError("A valid application date is required.");
  const year=today.getFullYear(),month=today.getMonth();
  let start:Date,end:Date;
  if(preset==="This Calendar Year" || preset==="Last Calendar Year") {
    const firstYear=year-(preset==="Last Calendar Year"?1:0);
    start=new Date(firstYear,0,1);end=new Date(firstYear,11,31);
  } else if(preset==="This Academic Year" || preset==="Last Academic Year") {
    const firstYear=year-(month<6?1:0)-(preset==="Last Academic Year"?1:0);
    start=new Date(firstYear,6,1);end=new Date(firstYear+1,5,30);
  } else if(preset==="This Month" || preset==="Last Month" || preset==="Previous Month") {
    const firstMonth=month-(preset==="This Month"?0:1);
    start=new Date(year,firstMonth,1);end=new Date(year,firstMonth+1,0);
  } else if(EXTRA_DATE_PRESETS.some(value=>value===preset)) {
    const width=preset.includes("Half-Year")?6:3;
    const firstMonth=Math.floor(month/width)*width-(preset.startsWith("Previous")?width:0);
    start=new Date(year,firstMonth,1);end=new Date(year,firstMonth+width,0);
  } else throw new RangeError(`No dates are calculated for ${preset}.`);
  return {from_date:iso(start),to_date:iso(end)};
}

function validDate(value:unknown):value is string {
  if(typeof value!=="string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date=new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0,10)===value;
}
export function validRange(value:unknown):value is DateRange {
  if(!value || typeof value!=="object") return false;
  const range=value as DateRange;
  return validDate(range.from_date) && validDate(range.to_date) && range.from_date<=range.to_date;
}
export const displayRange=(range:DateRange)=>`${range.from_date.split("-").reverse().join("-")} to ${range.to_date.split("-").reverse().join("-")}`;
