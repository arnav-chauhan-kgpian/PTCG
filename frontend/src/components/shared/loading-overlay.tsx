"use client";
import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";

export function LoadingOverlay({ message = "Loading…" }: { message?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[60] flex items-center justify-center bg-background/70 backdrop-blur-md"
    >
      <div className="flex flex-col items-center gap-3 glass-strong rounded-2xl p-8 shadow-2xl">
        <Loader2 className="size-8 text-electric animate-spin" />
        <p className="text-sm text-muted-foreground">{message}</p>
      </div>
    </motion.div>
  );
}
