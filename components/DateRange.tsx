"use client";
import {createContext,FormEvent,useContext,useEffect,useRef,useState} from "react";
import {usePathname} from "next/navigation";
import {DATE_PRESETS,DatePreset,DateRange,displayRange,EXTRA_DATE_PRESETS,isDatePreset,presetRange,validRange} from "@/lib/date-range";
export {presetRange,validRange} from "@/lib/date-range";
export type {DateRange} from "@/lib/date-range";

type RangeState = {range:DateRange;preset:DatePreset;ready:boolean;setRange:(range:DateRange,preset?:DatePreset)=>void};
const Context=createContext<RangeState|null>(null);
const key="faculty-report-date-range";
export function DateRangeProvider({children}:{children:React.ReactNode}) {
  const [range,setState]=useState<DateRange>({from_date:"",to_date:""});
  const [preset,setPreset]=useState<DatePreset>("Custom");
  const [ready,setReady]=useState(false);
  const selection=useRef<{range:DateRange;preset:DatePreset}|undefined>(undefined);
  const path=usePathname();
  function setRange(value:DateRange,chosen:DatePreset="Custom") {
    if(!validRange(value))return;
    // Keep preset labels out of the range object spread into reporting requests.
    const explicit={from_date:value.from_date,to_date:value.to_date};
    setState(explicit);setPreset(chosen);selection.current={range:explicit,preset:chosen};
    try{localStorage.setItem(key,JSON.stringify({...explicit,preset:chosen}));}catch{/* Selection remains available in memory. */}
  }
  useEffect(()=>{
    const params=new URLSearchParams(window.location.search);
    const requested={from_date:params.get("from_date")||"",to_date:params.get("to_date")||""};
    let chosen:DatePreset="This Academic Year",value=presetRange(chosen);
    if(selection.current) {
      chosen=selection.current.preset;
      value=chosen==="Custom"?selection.current.range:presetRange(chosen);
    } else {
      try {
        const saved=JSON.parse(localStorage.getItem(key)||"null");
        const storedPreset=saved?.preset;
        if(validRange(saved)) {
          chosen=isDatePreset(storedPreset)?storedPreset:"Custom";
          value=chosen==="Custom"?saved:presetRange(chosen);
        }
      } catch{/* Start with the current academic year when storage is unavailable. */}
    }
    if(validRange(requested)) {
      if(requested.from_date!==value.from_date || requested.to_date!==value.to_date) chosen="Custom";
      value=requested;
    }
    setRange(value,chosen);setReady(true);
  },[path]);
  return <Context.Provider value={{range,preset,ready,setRange}}>{children}</Context.Provider>;
}
export function useDateRange(){const state=useContext(Context);if(!state)throw new Error("DateRangeProvider missing");return state;}
export default function DateRangeFilter() {
  const {range,preset:appliedPreset,ready,setRange}=useDateRange();
  const [draft,setDraft]=useState(range);
  const [preset,setPreset]=useState<DatePreset>("Custom");
  const [error,setError]=useState("");
  const [initialized,setInitialized]=useState(false);
  useEffect(()=>{if(ready && validRange(range)){setDraft(range);setPreset(appliedPreset);setError("");setInitialized(true);}},[range,ready,appliedPreset]);
  function apply(event:FormEvent) {
    event.preventDefault();
    if(!validRange(draft)){setError("From Date and To Date are required; From Date must be on or before To Date.");return;}
    setError("");setRange(draft,preset);
  }
  return <section className="panel"><form className="date-range" onSubmit={apply} aria-label="Reporting date range">
    <label className="field">Date Range<select disabled={!initialized} value={preset} onChange={e=>{
      const chosen=e.target.value as DatePreset;setPreset(chosen);setError("");
      if(chosen!=="Custom") {const value=presetRange(chosen);setDraft(value);setRange(value,chosen);}
    }}>{DATE_PRESETS.map(value=><option key={value}>{value}</option>)}<optgroup label="Additional calendar ranges">{EXTRA_DATE_PRESETS.map(value=><option key={value}>{value}</option>)}</optgroup></select></label>
    <label className="field">From Date<input disabled={!initialized} required type="date" value={draft.from_date} onChange={e=>{setDraft({...draft,from_date:e.target.value});setPreset("Custom");}}/></label>
    <label className="field">To Date<input disabled={!initialized} required type="date" value={draft.to_date} onChange={e=>{setDraft({...draft,to_date:e.target.value});setPreset("Custom");}}/></label>
    <button disabled={!initialized} type="submit">Apply dates</button>
    <button disabled={!initialized} type="button" className="secondary" onClick={()=>{const value=presetRange('This Academic Year');setDraft(value);setPreset('This Academic Year');setRange(value,'This Academic Year');setError('');}}>Reset</button>
  </form>{error && <div className="error" role="alert">{error}</div>}
  <p className="muted range-caption">{validRange(draft)?`${preset} · ${displayRange(draft)} · Inclusive dates`:'Choose From Date and To Date.'} · Selection carries between reports. Academic year: July 1–June 30.{(draft.from_date!==range.from_date || draft.to_date!==range.to_date) && ' Apply dates to update reports.'}</p></section>;
}
