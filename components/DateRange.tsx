"use client";
import {createContext,useContext,useEffect,useId,useRef,useState,type ReactNode} from "react";
import {usePathname} from "next/navigation";
import {DATE_PRESETS,DatePreset,DateRange,displayRange,EXTRA_DATE_PRESETS,isDatePreset,presetRange,validRange} from "@/lib/date-range";
export {presetRange,validRange} from "@/lib/date-range";
export type {DateRange} from "@/lib/date-range";

type RangeState = {range:DateRange;preset:DatePreset;ready:boolean;setRange:(range:DateRange,preset?:DatePreset)=>void;resetRange:()=>void};
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
  function resetRange() { setRange(presetRange("This Academic Year"), "This Academic Year"); }
  useEffect(()=>{
    const params=new URLSearchParams(window.location.search);
    const requested={from_date:params.get("from_date")||"",to_date:params.get("to_date")||""};
    const requestedPreset=params.get("reporting_preset");
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
    // Header navigation carries the selected named preset explicitly. Its
    // concrete bounds are useful to server-rendered links, but they must not
    // turn a dynamic preset into a stale Custom range on the next route.
    if(requestedPreset && requestedPreset !== "Custom" && isDatePreset(requestedPreset)) {
      chosen=requestedPreset;
      value=presetRange(chosen);
    } else if(validRange(requested)) {
      if(requested.from_date!==value.from_date || requested.to_date!==value.to_date) chosen="Custom";
      value=requested;
    }
    setRange(value,chosen);setReady(true);
  },[path]);
  return <Context.Provider value={{range,preset,ready,setRange,resetRange}}>{children}</Context.Provider>;
}
export function useDateRange(){const state=useContext(Context);if(!state)throw new Error("DateRangeProvider missing");return state;}
export function DateRangeSummary() {
  const { range, preset } = useDateRange();
  return <p className="muted overview-range-summary">{validRange(range) ? `Applied: ${preset === "Custom" ? "Custom Range" : preset} · ${displayRange(range)} · Inclusive dates` : "Choose From Date and To Date."}</p>;
}

export function OverviewDateRangeControl({ children }: { children: (parts: { gridControl: ReactNode; footerControl: ReactNode }) => ReactNode }) {
  const { range, preset: appliedPreset, ready, setRange } = useDateRange();
  const [draft, setDraft] = useState(range);
  const [preset, setPreset] = useState<DatePreset>("Custom");
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  const dialogId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const fromDateRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (ready && validRange(range)) {
      setDraft(range); setPreset(appliedPreset); setError(""); setOpen(false);
    }
  }, [range, ready, appliedPreset]);

  useEffect(() => {
    if (!open) return;
    fromDateRef.current?.focus({ preventScroll: true });
    const dismiss = () => { setDraft(range); setPreset(appliedPreset); setError(""); setOpen(false); };
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") dismiss(); };
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!dialogRef.current?.contains(target) && !triggerRef.current?.contains(target)) dismiss();
    };
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("pointerdown", onPointerDown);
    return () => { document.removeEventListener("keydown", onKeyDown); document.removeEventListener("pointerdown", onPointerDown); };
  }, [open, range, appliedPreset]);

  const closeWithoutApplying = () => {
    setDraft(range); setPreset(appliedPreset); setError(""); setOpen(false); triggerRef.current?.focus();
  };
  const apply = () => {
    if (!validRange(draft)) { setError("From Date and To Date are required; From Date must be on or before To Date."); return; }
    setError(""); setRange(draft, "Custom"); setOpen(false); triggerRef.current?.focus();
  };
  const gridControl = <div className="filter-field">
    <label className="field">Reporting Period<select disabled={!ready} value={preset} onChange={(event) => {
      const chosen = event.target.value as DatePreset;
      setPreset(chosen); setError("");
      if (chosen !== "Custom") { const value = presetRange(chosen); setDraft(value); setRange(value, chosen); setOpen(false); }
    }}>{DATE_PRESETS.map(value => <option key={value} value={value}>{value === "Custom" ? "Custom Range" : value === "Last Academic Year" ? "Previous Academic Year" : value}</option>)}<optgroup label="Additional calendar ranges">{EXTRA_DATE_PRESETS.map(value => <option key={value}>{value}</option>)}</optgroup></select></label>
  </div>;
  const footerControl = preset === "Custom" ? <div className="overview-date-actions"><button ref={triggerRef} type="button" className="secondary small" aria-expanded={open} aria-controls={dialogId} onClick={() => { setError(""); setOpen(true); }}>Set dates</button>{open && <div ref={dialogRef} id={dialogId} className="date-range-popover" role="dialog" aria-label="Custom date range">
    <div className="date-range-popover-fields"><label className="field">From Date<input ref={fromDateRef} required type="date" value={draft.from_date} onChange={event => setDraft({ ...draft, from_date: event.target.value })} /></label><label className="field">To Date<input required type="date" value={draft.to_date} onChange={event => setDraft({ ...draft, to_date: event.target.value })} /></label></div>
    {error && <div className="error" role="alert">{error}</div>}
    <div className="actions"><button type="button" className="secondary small" onClick={closeWithoutApplying}>Cancel</button><button type="button" className="small" onClick={apply}>Apply range</button></div>
  </div>}</div> : null;
  return children({ gridControl, footerControl });
}

export default function DateRangeFilter() {
  const {range,preset:appliedPreset,ready,setRange,resetRange}=useDateRange();
  const [draft,setDraft]=useState(range);
  const [preset,setPreset]=useState<DatePreset>("Custom");
  const [error,setError]=useState("");
  const [initialized,setInitialized]=useState(false);
  useEffect(()=>{if(ready && validRange(range)){setDraft(range);setPreset(appliedPreset);setError("");setInitialized(true);}},[range,ready,appliedPreset]);
  function apply() {
    if(!validRange(draft)){setError("From Date and To Date are required; From Date must be on or before To Date.");return;}
    setError("");setRange(draft,preset);
  }
  const showCustomRange = preset === "Custom";
  const periodControl = <label className="field">Reporting Period<select disabled={!initialized} value={preset} onChange={e=>{
      const chosen=e.target.value as DatePreset;setPreset(chosen);setError("");
      if(chosen!=="Custom") {const value=presetRange(chosen);setDraft(value);setRange(value,chosen);}
    }}>{DATE_PRESETS.map(value=><option key={value} value={value}>{value==="Custom"?"Custom Range":value==="Last Academic Year"?"Previous Academic Year":value}</option>)}<optgroup label="Additional calendar ranges">{EXTRA_DATE_PRESETS.map(value=><option key={value}>{value}</option>)}</optgroup></select></label>;
  const customControls = showCustomRange&&<><label className="field">From Date<input disabled={!initialized} required type="date" value={draft.from_date} onChange={e=>{setDraft({...draft,from_date:e.target.value});}}/></label>
    <label className="field">To Date<input disabled={!initialized} required type="date" value={draft.to_date} onChange={e=>{setDraft({...draft,to_date:e.target.value});}}/></label>
    <button disabled={!initialized} type="button" onClick={apply}>Apply range</button></>;
  return <section className="reporting-period"><form className="date-range" onSubmit={(event) => { event.preventDefault(); apply(); }} aria-label="Reporting period">{periodControl}{customControls}<button disabled={!initialized} type="button" className="secondary" onClick={()=>{resetRange();setError("");}}>Reset</button></form>{error && <div className="error" role="alert">{error}</div>}
  <p className="muted range-caption">{validRange(draft)?`${preset==="Custom"?"Custom Range":preset} · ${displayRange(draft)} · Inclusive dates`:'Choose From Date and To Date.'} · Selection carries between reports.{(draft.from_date!==range.from_date || draft.to_date!==range.to_date) && ' Apply the custom range to update reports.'}</p></section>;
}
