"use client";
import { motion } from "framer-motion";
import { Bell, Github, Moon, Palette, Settings as SettingsIcon, Sun, User } from "lucide-react";
import { useTheme } from "next-themes";
import * as React from "react";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { siteConfig } from "@/config/site";

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  return (
    <div className="container max-w-4xl py-6 md:py-10 space-y-6">
      <PageHeader title="Settings" description="Customize your workspace, theme, and integrations." icon={<SettingsIcon className="size-5" />} />

      <Section icon={User} title="Account" description="Your profile information">
        <Field label="Display name" defaultValue="Pokémon AI Researcher" />
        <Field label="Email" defaultValue="hello@pokemon-ai.dev" />
      </Section>

      <Section icon={Palette} title="Appearance" description="Theme and visual preferences">
        <div className="flex items-center gap-2">
          <Button variant={theme === "dark" ? "gradient" : "glass"} size="sm" onClick={() => setTheme("dark")}>
            <Moon className="size-4" /> Dark
          </Button>
          <Button variant={theme === "light" ? "gradient" : "glass"} size="sm" onClick={() => setTheme("light")}>
            <Sun className="size-4" /> Light
          </Button>
          <Button variant={theme === "system" ? "gradient" : "glass"} size="sm" onClick={() => setTheme("system")}>
            System
          </Button>
        </div>
      </Section>

      <Section icon={Bell} title="Notifications" description="Alerts for training and promotions">
        <ToggleRow label="Training round complete" defaultEnabled />
        <ToggleRow label="Candidate promotion" defaultEnabled />
        <ToggleRow label="Benchmark regression" />
      </Section>

      <Section icon={Github} title="Integrations" description="Connect external services">
        <Row label="Backend URL" value={process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"} mono />
        <Row label="Site URL" value={siteConfig.url} mono />
        <Row label="App version" value="v1.0.0" />
      </Section>
    </div>
  );
}

function Section({ icon: Icon, title, description, children }: { icon: any; title: string; description: string; children: React.ReactNode }) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="rounded-2xl border border-border/40 bg-card/40 backdrop-blur-xl p-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="size-10 rounded-xl border border-border/60 bg-background/60 grid place-items-center text-electric">
          <Icon className="size-4" />
        </div>
        <div>
          <p className="font-semibold text-sm">{title}</p>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
      </div>
      <div className="space-y-3">{children}</div>
    </motion.div>
  );
}
function Field({ label, defaultValue }: { label: string; defaultValue: string }) {
  return (
    <div>
      <label className="text-xs text-muted-foreground mb-1 block">{label}</label>
      <Input defaultValue={defaultValue} />
    </div>
  );
}
function ToggleRow({ label, defaultEnabled }: { label: string; defaultEnabled?: boolean }) {
  const [on, setOn] = React.useState(defaultEnabled ?? false);
  return (
    <div className="flex items-center justify-between rounded-lg border border-border/30 bg-background/30 p-3">
      <span className="text-sm">{label}</span>
      <button
        onClick={() => setOn((s) => !s)}
        className={`relative h-6 w-11 rounded-full transition-colors ${on ? "bg-brand-gradient" : "bg-muted"}`}
        aria-pressed={on}
      >
        <span className={`absolute top-1 size-4 rounded-full bg-white transition-transform ${on ? "left-6" : "left-1"}`} />
      </button>
    </div>
  );
}
function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-border/30 bg-background/30 p-3">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className={`text-sm font-semibold tabular-nums ${mono ? "font-mono" : ""}`}>{value}</span>
    </div>
  );
}
