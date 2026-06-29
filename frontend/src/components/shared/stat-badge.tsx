import { cn } from "@/lib/utils";

export function StatBadge({
  label, value, accent = "default",
}: {
  label: string;
  value: string | number;
  accent?: "default" | "electric" | "purple" | "gold" | "emerald";
}) {
  const colors = {
    default: "border-border/60 bg-card/60",
    electric: "border-electric/30 bg-electric/10 text-electric",
    purple: "border-purple/30 bg-purple/10 text-purple-light",
    gold: "border-gold/30 bg-gold/10 text-gold-light",
    emerald: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  };
  return (
    <div className={cn("inline-flex flex-col gap-0.5 rounded-lg border px-3 py-2 backdrop-blur", colors[accent])}>
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">{label}</span>
      <span className="text-sm font-semibold tabular-nums">{value}</span>
    </div>
  );
}
