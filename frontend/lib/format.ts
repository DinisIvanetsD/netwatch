import type { Device } from "@/types/device";

export function formatLatency(latencyMs: number | null): string {
  if (latencyMs === null) return "—";
  return `${latencyMs.toFixed(latencyMs < 10 ? 1 : 0)} ms`;
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function formatRelativeTime(value: string, now = Date.now()): string {
  const differenceSeconds = Math.round(
    (new Date(value).getTime() - now) / 1000,
  );
  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  const ranges: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ["year", 31_536_000],
    ["month", 2_592_000],
    ["day", 86_400],
    ["hour", 3_600],
    ["minute", 60],
  ];

  for (const [unit, seconds] of ranges) {
    if (Math.abs(differenceSeconds) >= seconds) {
      return formatter.format(Math.round(differenceSeconds / seconds), unit);
    }
  }
  return formatter.format(differenceSeconds, "second");
}

export function deviceDisplayName(
  device: Pick<Device, "name" | "hostname" | "ip_address">,
): string {
  if (device.name && device.name !== device.ip_address) return device.name;
  if (device.hostname && device.hostname !== device.ip_address) {
    return device.hostname;
  }
  return "Unnamed device";
}
