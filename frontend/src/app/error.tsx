"use client";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="min-h-screen mesh-bg flex items-center justify-center px-4">
      <div className="text-center max-w-md">
        <div className="size-20 mx-auto rounded-3xl bg-gradient-to-br from-rose-500 to-purple shadow-2xl shadow-rose-500/30 grid place-items-center mb-6">
          <AlertTriangle className="size-9 text-white" />
        </div>
        <h1 className="font-display font-bold text-3xl md:text-4xl mb-2">Something went wrong</h1>
        <p className="text-sm text-muted-foreground mb-2 leading-relaxed">
          {error.message || "An unexpected error occurred."}
        </p>
        {error.digest && (
          <p className="text-xs font-mono text-muted-foreground/70 mb-6">{error.digest}</p>
        )}
        <Button onClick={reset} variant="gradient">
          <RefreshCw className="size-4" /> Try again
        </Button>
      </div>
    </div>
  );
}
