"use client";
import type * as React from "react";
import { cn } from "@/lib/utils";

export function ChartCard({
  title, description, action, children, className, height = "h-72",
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  height?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-border/40 bg-card/40 backdrop-blur-xl p-6 shadow-xl",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="space-y-1">
          <h3 className="font-semibold text-sm">{title}</h3>
          {description && <p className="text-xs text-muted-foreground">{description}</p>}
        </div>
        {action}
      </div>
      <div className={cn("w-full", height)}>{children}</div>
    </div>
  );
}
