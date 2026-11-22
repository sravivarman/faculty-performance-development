"use client";

import { Children, type ReactNode } from "react";
import { DateRangeSummary, OverviewDateRangeControl, useDateRange } from "@/components/DateRange";

export default function OverviewFilterPanel({ children, footer, onResetFilters }: { children: ReactNode; footer?: ReactNode; onResetFilters: () => void }) {
  const { resetRange } = useDateRange();
  return <section className="overview-filter-panel" aria-label="Overview filters">
    <div className="overview-filter-heading"><h2>Filters</h2><button type="button" className="secondary" onClick={() => { resetRange(); onResetFilters(); }}>Reset Filters</button></div>
    <OverviewDateRangeControl>{({ gridControl, footerControl }) => <><div className="overview-filter-grid">{gridControl}{Children.toArray(children).filter(Boolean).map((child, index) => <div className="filter-field" key={index}>{child}</div>)}</div>
      <div className="overview-filter-footer"><DateRangeSummary />{footerControl}{footer}</div></>}</OverviewDateRangeControl>
  </section>;
}
