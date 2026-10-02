"use client";
// Tremor Raw Table v1.0.0, adapted to prefixed utilities and compact light styling.
// https://www.tremor.so/docs/ui/table — Apache-2.0, see TREMOR-LICENSE.
import React from 'react';
import {clsx} from 'clsx';
export const TableRoot=React.forwardRef<HTMLDivElement,React.HTMLAttributes<HTMLDivElement>>(({className,...props},ref)=><div ref={ref} className={clsx('tw:w-full tw:overflow-auto',className)} {...props}/>);
export const Table=React.forwardRef<HTMLTableElement,React.TableHTMLAttributes<HTMLTableElement>>(({className,...props},ref)=><table ref={ref} tremor-id="tremor-raw" className={clsx('tw:w-full tw:caption-bottom tw:border-b tw:border-gray-200',className)} {...props}/>);
export const TableHead=React.forwardRef<HTMLTableSectionElement,React.HTMLAttributes<HTMLTableSectionElement>>((props,ref)=><thead ref={ref} {...props}/>);
export const TableBody=React.forwardRef<HTMLTableSectionElement,React.HTMLAttributes<HTMLTableSectionElement>>((props,ref)=><tbody ref={ref} {...props}/>);
export const TableRow=React.forwardRef<HTMLTableRowElement,React.HTMLAttributes<HTMLTableRowElement>>((props,ref)=><tr ref={ref} {...props}/>);
export const TableHeaderCell=React.forwardRef<HTMLTableCellElement,React.ThHTMLAttributes<HTMLTableCellElement>>(({className,...props},ref)=><th ref={ref} className={clsx('tw:border-b tw:border-gray-200 tw:text-left tw:text-xs tw:font-semibold',className)} {...props}/>);
export const TableCell=React.forwardRef<HTMLTableCellElement,React.TdHTMLAttributes<HTMLTableCellElement>>(({className,...props},ref)=><td ref={ref} className={clsx('tw:text-xs tw:text-gray-600',className)} {...props}/>);
TableRoot.displayName='TableRoot';Table.displayName='Table';TableHead.displayName='TableHead';TableBody.displayName='TableBody';TableRow.displayName='TableRow';TableHeaderCell.displayName='TableHeaderCell';TableCell.displayName='TableCell';
