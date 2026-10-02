"use client";
import Link from 'next/link';
import {useDateRange} from '@/components/DateRange';
export default function ResearchModulesMenu(){const {range}=useDateRange();const dates=new URLSearchParams(range).toString();return <details className="research-modules-menu"><summary>More research</summary><div>{Object.entries({fdp:'FDP / Workshop / Seminar',certifications:'Certifications',proposals:'Research Proposals',consultancy:'Consultancy'}).map(([path,title])=><Link key={path} href={`/${path}?${dates}`}>{title}</Link>)}</div></details>;}
