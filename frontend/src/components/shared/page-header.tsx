"use client";
import { motion } from "framer-motion";
import type * as React from "react";

export function PageHeader({
  title, description, actions, icon,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  icon?: React.ReactNode;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"
    >
      <div className="flex items-start gap-4">
        {icon && (
          <div className="flex size-12 items-center justify-center rounded-2xl bg-brand-gradient text-white shadow-lg shadow-electric/30 [background-size:200%_100%] animate-gradient-flow">
            {icon}
          </div>
        )}
        <div className="space-y-1.5">
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight font-display">
            {title}
          </h1>
          {description && (
            <p className="text-sm md:text-base text-muted-foreground max-w-2xl">
              {description}
            </p>
          )}
        </div>
      </div>
      {actions && <div className="flex gap-2 shrink-0">{actions}</div>}
    </motion.div>
  );
}
