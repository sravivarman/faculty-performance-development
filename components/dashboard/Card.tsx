"use client";
// Tremor Raw Card v1.0.0, adapted with prefixed utilities and a light dashboard theme.
// Source: https://www.tremor.so/docs/ui/card (Apache-2.0; see TREMOR-LICENSE).
import React from "react";
import {Slot} from "@radix-ui/react-slot";
import {clsx} from "clsx";
import {extendTailwindMerge} from "tailwind-merge";
const merge=extendTailwindMerge({prefix:"tw"});
export interface CardProps extends React.ComponentPropsWithoutRef<"div"> {asChild?:boolean}
export const Card=React.forwardRef<HTMLDivElement,CardProps>(({className,asChild,...props},ref)=>{
  const Component=asChild?Slot:"div";
  return <Component ref={ref} className={merge(clsx("tw:relative tw:w-full tw:rounded-lg tw:border tw:border-solid tw:border-gray-200 tw:bg-white tw:p-6 tw:text-left tw:shadow-xs",className))} tremor-id="tremor-raw" {...props}/>;
});
Card.displayName="Card";
