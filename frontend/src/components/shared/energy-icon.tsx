import { cn } from "@/lib/utils";

const energyConfig: Record<string, { color: string; symbol: string; label: string }> = {
  R: { color: "bg-type-fire text-white", symbol: "🔥", label: "Fire" },
  W: { color: "bg-type-water text-white", symbol: "💧", label: "Water" },
  G: { color: "bg-type-grass text-white", symbol: "🌿", label: "Grass" },
  L: { color: "bg-type-lightning text-black", symbol: "⚡", label: "Lightning" },
  P: { color: "bg-type-psychic text-white", symbol: "🔮", label: "Psychic" },
  F: { color: "bg-type-fighting text-white", symbol: "👊", label: "Fighting" },
  D: { color: "bg-type-dark text-white", symbol: "🌑", label: "Darkness" },
  M: { color: "bg-type-metal text-black", symbol: "⚙", label: "Metal" },
  N: { color: "bg-type-dragon text-white", symbol: "🐉", label: "Dragon" },
  C: { color: "bg-type-colorless text-black", symbol: "★", label: "Colorless" },
  Y: { color: "bg-type-fairy text-white", symbol: "✨", label: "Fairy" },
};

export function EnergyIcon({
  type,
  size = "md",
  className,
}: {
  type: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const key = type.replace(/[{}]/g, "");
  const cfg = energyConfig[key] || energyConfig.C;
  const dims = size === "sm" ? "size-4 text-[10px]" : size === "lg" ? "size-7 text-base" : "size-5 text-xs";
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center rounded-full font-bold shadow shrink-0",
        cfg.color,
        dims,
        className,
      )}
      title={cfg.label}
    >
      {cfg.symbol}
    </span>
  );
}
