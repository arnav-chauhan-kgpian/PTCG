"use client";
import {
  Area,
  AreaChart as RechartsAreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface Props<T extends Record<string, unknown>> {
  data: T[];
  xKey: keyof T & string;
  series: { key: keyof T & string; label: string; color: string }[];
  yFormatter?: (v: number) => string;
  xFormatter?: (v: unknown) => string;
}

export function AreaChart<T extends Record<string, unknown>>({
  data, xKey, series, yFormatter, xFormatter,
}: Props<T>) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <RechartsAreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <defs>
          {series.map((s) => (
            <linearGradient key={s.key} id={`grad-${s.key}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={s.color} stopOpacity={0.45} />
              <stop offset="100%" stopColor={s.color} stopOpacity={0.02} />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid strokeDasharray="3 6" stroke="hsl(var(--border))" vertical={false} opacity={0.35} />
        <XAxis
          dataKey={xKey}
          stroke="hsl(var(--muted-foreground))"
          tick={{ fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={xFormatter as any}
        />
        <YAxis
          stroke="hsl(var(--muted-foreground))"
          tick={{ fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={yFormatter}
          width={45}
        />
        <Tooltip
          contentStyle={{
            background: "hsl(var(--popover))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "0.5rem",
            fontSize: "12px",
            boxShadow: "0 10px 25px rgba(0,0,0,0.3)",
          }}
          formatter={(v) => (typeof v === "number" ? (yFormatter ? yFormatter(v) : v) : v)}
        />
        {series.map((s) => (
          <Area
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.label}
            stroke={s.color}
            strokeWidth={2}
            fill={`url(#grad-${s.key})`}
            isAnimationActive
            animationDuration={900}
          />
        ))}
      </RechartsAreaChart>
    </ResponsiveContainer>
  );
}
