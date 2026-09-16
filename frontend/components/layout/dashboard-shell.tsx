"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Ban,
  Bell,
  ChevronRight,
  CircleDot,
  FileText,
  Gauge,
  History,
  Globe2,
  Menu,
  Network,
  Radar,
  ServerCog,
  Settings,
  ShieldAlert,
  ShieldCheck,
  X,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScanButton } from "@/components/scans/scan-button";
import { formatRelativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { OperatingMode } from "@/types/settings";
import {
  type SocketStatus,
  useNetWatchSocket,
} from "@/hooks/use-netwatch-socket";

const navigation = [
  {
    label: "",
    items: [{ href: "/dashboard", label: "Overview", icon: Gauge }],
  },
  {
    label: "Monitoring",
    items: [
      { href: "/devices", label: "Devices", icon: ServerCog },
      { href: "/network", label: "Network", icon: Network },
      { href: "/services", label: "Services", icon: Radar },
      { href: "/alerts", label: "Alerts", icon: ShieldAlert },
    ],
  },
  {
    label: "Analysis",
    items: [
      { href: "/activity", label: "Activity", icon: Activity },
      { href: "/internet", label: "Internet", icon: Globe2 },
      { href: "/history", label: "History", icon: History },
      { href: "/reports", label: "Reports", icon: FileText },
    ],
  },
  {
    label: "Control",
    items: [
      {
        href: "/parental-controls",
        label: "Parental Controls",
        icon: ShieldCheck,
      },
      { href: "/access-control", label: "Access Control", icon: CircleDot },
      { href: "/blocked", label: "Website Blocking", icon: Ban },
    ],
  },
  {
    label: "System",
    items: [{ href: "/settings", label: "Settings", icon: Settings }],
  },
];

const pageNames: Record<string, string> = {
  "/dashboard": "Overview",
  "/devices": "Devices",
  "/network": "Network",
  "/services": "Services",
  "/alerts": "Alerts",
  "/activity": "Activity",
  "/internet": "Internet Activity",
  "/history": "History",
  "/reports": "Network Report",
  "/parental-controls": "Parental Controls",
  "/access-control": "Access Control",
  "/blocked": "Website Blocking",
  "/settings": "Settings",
};

function SidebarContent({
  onNavigate,
  status,
  scanRunning,
}: {
  onNavigate?: () => void;
  status: SocketStatus;
  scanRunning: boolean;
}) {
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col">
      <div className="border-border flex h-16 items-center gap-3 border-b px-5">
        <span className="bg-primary text-primary-foreground grid size-8 place-items-center rounded-lg">
          <Radar className="size-4" aria-hidden="true" />
        </span>
        <div>
          <p className="text-sm font-bold tracking-[0.14em]">NETWATCH</p>
          <p className="text-muted-foreground text-[10px]">
            NETWORK INTELLIGENCE
          </p>
        </div>
      </div>

      <nav
        className="flex-1 space-y-6 overflow-y-auto p-3"
        aria-label="Primary navigation"
      >
        {navigation.map((section, sectionIndex) => (
          <div key={`${section.label}-${sectionIndex}`}>
            {section.label ? (
              <p className="text-muted-foreground/70 mb-2 px-3 text-[10px] font-semibold tracking-[0.16em] uppercase">
                {section.label}
              </p>
            ) : null}
            <div className="space-y-1">
              {section.items.map((item) => {
                const active =
                  pathname === item.href ||
                  pathname.startsWith(`${item.href}/`);
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onNavigate}
                    className={cn(
                      "group flex h-9 items-center gap-3 rounded-md px-3 text-sm transition-colors",
                      active
                        ? "bg-accent text-foreground"
                        : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
                    )}
                    aria-current={active ? "page" : undefined}
                  >
                    <Icon className="size-4" aria-hidden="true" />
                    <span>{item.label}</span>
                    {active ? (
                      <ChevronRight className="ms-auto size-3.5 opacity-60" />
                    ) : null}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="border-border border-t p-4">
        <div className="flex items-center justify-between text-xs">
          <div>
            <p className="text-foreground font-medium">Scanner</p>
            <p className="text-muted-foreground mt-1 flex items-center gap-1.5">
              <CircleDot
                className="size-3 text-emerald-400"
                aria-hidden="true"
              />
              {scanRunning
                ? "Scan running"
                : status === "connected"
                  ? "Live connected"
                  : status === "offline"
                    ? "Offline"
                    : "Connecting"}
            </p>
          </div>
          <span className="text-muted-foreground font-mono text-[10px]">
            v1.0.0
          </span>
        </div>
      </div>
    </div>
  );
}

export function DashboardShell({
  children,
  operatingMode,
  lastCompletedScan,
  scanRunning,
  activeAlerts,
}: Readonly<{
  children: React.ReactNode;
  operatingMode: OperatingMode;
  lastCompletedScan: string | null;
  scanRunning: boolean;
  activeAlerts: number;
}>) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { status } = useNetWatchSocket();
  const pathname = usePathname();
  const currentPage = pathname.startsWith("/devices/")
    ? "Device Details"
    : (pageNames[pathname] ?? "NetWatch");

  useEffect(() => {
    if (!mobileOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = "";
    };
  }, [mobileOpen]);

  return (
    <div className="bg-background min-h-dvh">
      <aside className="border-border bg-card fixed inset-y-0 start-0 z-40 hidden w-60 border-e lg:block">
        <SidebarContent status={status} scanRunning={scanRunning} />
      </aside>

      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            className="absolute inset-0 bg-black/60"
            aria-label="Close navigation"
            onClick={() => setMobileOpen(false)}
          />
          <aside
            className="border-border bg-card relative h-full w-72 border-e shadow-2xl"
            role="dialog"
            aria-modal="true"
            aria-label="Navigation menu"
          >
            <Button
              variant="ghost"
              size="icon"
              className="absolute end-3 top-3 z-10"
              onClick={() => setMobileOpen(false)}
              aria-label="Close navigation"
            >
              <X />
            </Button>
            <SidebarContent
              status={status}
              scanRunning={scanRunning}
              onNavigate={() => setMobileOpen(false)}
            />
          </aside>
        </div>
      ) : null}

      <div className="lg:ps-60">
        <header className="border-border bg-background/95 sticky top-0 z-30 flex h-16 items-center gap-3 border-b px-4 backdrop-blur md:px-6">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            onClick={() => setMobileOpen(true)}
            aria-label="Open navigation"
          >
            <Menu />
          </Button>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold">{currentPage}</p>
            <p
              className="text-muted-foreground hidden text-xs sm:block"
              aria-live="polite"
            >
              Network status: {status === "connected" ? "live" : status}
            </p>
          </div>
          <div className="ms-auto flex items-center gap-2">
            {operatingMode === "simulation" ? (
              <Badge
                variant="warning"
                title="This device is simulating the network. No real LAN is being scanned."
              >
                SIMULATED NETWORK
              </Badge>
            ) : (
              <Badge
                variant="success"
                title="This device is monitoring the real devices on your authorized network."
              >
                LIVE SENSOR
              </Badge>
            )}
            <p
              className="text-muted-foreground hidden text-xs xl:block"
              suppressHydrationWarning
            >
              Last scan:{" "}
              {lastCompletedScan
                ? formatRelativeTime(lastCompletedScan)
                : "never"}
            </p>
            <ScanButton />
            <Button
              variant="ghost"
              size="icon"
              asChild
              aria-label={`${activeAlerts} active alerts`}
            >
              <Link href="/alerts" className="relative">
                <Bell />
                {activeAlerts ? (
                  <span className="bg-destructive absolute end-0 top-0 grid size-4 place-items-center rounded-full text-[9px] font-bold text-white">
                    {Math.min(activeAlerts, 9)}
                  </span>
                ) : null}
              </Link>
            </Button>
            <Button
              variant="ghost"
              size="icon"
              asChild
              aria-label="Open settings"
            >
              <Link href="/settings">
                <Settings />
              </Link>
            </Button>
          </div>
        </header>
        <main
          id="main-content"
          tabIndex={-1}
          className="mx-auto w-full max-w-[1600px] p-4 outline-none md:p-6 lg:p-8"
        >
          {children}
        </main>
      </div>
    </div>
  );
}
