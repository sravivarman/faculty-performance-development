"use client";
import {PATENT_TYPES} from '@/lib/patents';

export default function PatentTypeSelect({value,onChange,filter=false}:{value:string;onChange:(value:string)=>void;filter?:boolean}){
  return <label className="field">Patent Type<select required={!filter} value={value} onChange={e=>onChange(e.target.value)}><option value="">{filter?'All patent types':'Select patent type'}</option>{Object.entries(PATENT_TYPES).map(([value,name])=><option key={value} value={value}>{name}</option>)}</select></label>;
}
