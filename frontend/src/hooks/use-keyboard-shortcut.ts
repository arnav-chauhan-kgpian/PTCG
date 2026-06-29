"use client";
import * as React from "react";

interface ShortcutOpts {
  key: string;
  meta?: boolean;
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
  onTrigger: () => void;
  preventDefault?: boolean;
}

export function useKeyboardShortcut(opts: ShortcutOpts) {
  React.useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const matchesKey = e.key.toLowerCase() === opts.key.toLowerCase();
      const matchesMeta = opts.meta ? e.metaKey : !opts.meta || !e.metaKey;
      const matchesCtrl = opts.ctrl ? e.ctrlKey : !opts.ctrl || !e.ctrlKey;
      const matchesShift = opts.shift ? e.shiftKey : !opts.shift || !e.shiftKey;
      const matchesAlt = opts.alt ? e.altKey : !opts.alt || !e.altKey;
      // For ⌘K-style shortcuts: require meta OR ctrl
      const cmdOrCtrl = (opts.meta || opts.ctrl) ? (e.metaKey || e.ctrlKey) : true;
      if (matchesKey && cmdOrCtrl && matchesShift && matchesAlt) {
        if (opts.preventDefault) e.preventDefault();
        opts.onTrigger();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [opts]);
}
