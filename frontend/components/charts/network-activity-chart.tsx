"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { NetworkActivityPoint } from "@/types/network";

const timestampFormatter = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  hour: "2-digit",
  timeZone: "UTC",
});

export function NetworkActivityChart({
  points,
}: {
  points: NetworkActivityPoint[];
}) {
  const data = points.map((point) => ({
    ...point,
    label: timestampFormatter.format(new Date(point.timestamp)),
  }));
  return (
    <div
      className="h-72 w-full"
      role="img"
      aria-label="Network activity chart showing online devices, average latency and events"
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data}
          margin={{ top: 12, right: 12, left: -18, bottom: 0 }}
        >
          <CartesianGrid
            stroke="var(--border)"
            strokeDasharray="3 3"
            vertical={false}
          />
          <XAxis
            dataKey="label"
            tick={{ fill: "var(--muted-foreground)", fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            minTickGap={36}
          />
          <YAxis
            yAxisId="count"
            tick={{ fill: "var(--muted-foreground)", fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            allowDecimals={false}
          />
          <YAxis
            yAxisId="latency"
            orientation="right"
            tick={{ fill: "var(--muted-foreground)", fontSize: 10 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={{
              background: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              fontSize: 12,
            }}
          />
          <Line
            yAxisId="count"
            type="monotone"
            dataKey="online_devices"
            name="Online devices"
            stroke="var(--primary)"
            strokeWidth={2}
            dot={false}
          />
          <Line
            yAxisId="latency"
            type="monotone"
            dataKey="average_latency_ms"
            name="Latency (ms)"
            stroke="#f59e0b"
            strokeWidth={1.5}
            dot={false}
          />
          <Line
            yAxisId="count"
            type="monotone"
            dataKey="events"
            name="Events"
            stroke="#a78bfa"
            strokeWidth={1.5}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
