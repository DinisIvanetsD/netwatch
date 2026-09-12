"use client";

import { Download, Printer } from "lucide-react";
import { useCallback, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toCsv } from "@/lib/csv";
import { deviceDisplayName } from "@/lib/format";
import type { Alert } from "@/types/alert";
import type { Device } from "@/types/device";
import type { InternetActivityItem } from "@/types/internet-activity";

type ReportData = {
  devices: Device[];
  alerts: Alert[];
  dnsActivity: InternetActivityItem[];
  dnsAvailable: boolean;
};

function downloadCsv(filename: string, content: string) {
  const url = URL.createObjectURL(
    new Blob([content], { type: "text/csv;charset=utf-8" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  window.setTimeout(() => {
    URL.revokeObjectURL(url);
    link.remove();
  }, 0);
}

export function NetworkReport({ data }: { data: ReportData }) {
  const [exported, setExported] = useState("");
  const exportReport = useCallback(
    (kind: "devices" | "alerts" | "dns") => {
      if (kind === "devices") {
        downloadCsv(
          "netwatch-devices.csv",
          toCsv(data.devices, [
            { key: "id", label: "ID" },
            { key: "name", label: "Name" },
            { key: "hostname", label: "Hostname" },
            { key: "ip_address", label: "IP address" },
            { key: "status", label: "Status" },
            { key: "trust_state", label: "Trust state" },
            { key: "last_seen", label: "Last seen" },
          ]),
        );
        setExported("Devices CSV downloaded.");
      } else if (kind === "alerts") {
        downloadCsv(
          "netwatch-alerts.csv",
          toCsv(data.alerts, [
            { key: "id", label: "ID" },
            { key: "title", label: "Title" },
            { key: "severity", label: "Severity" },
            { key: "device_name", label: "Device" },
            { key: "read", label: "Read" },
            { key: "resolved", label: "Resolved" },
            { key: "created_at", label: "Created at" },
          ]),
        );
        setExported("Alerts CSV downloaded.");
      } else {
        downloadCsv(
          "netwatch-dns-activity.csv",
          toCsv(data.dnsActivity, [
            { key: "timestamp", label: "Timestamp" },
            { key: "device_name", label: "Device" },
            { key: "domain", label: "Domain" },
            { key: "category", label: "Category" },
            { key: "response_status", label: "Response" },
            { key: "blocked", label: "Blocked" },
          ]),
        );
        setExported("DNS activity CSV downloaded.");
      }
    },
    [data],
  );

  return (
    <div className="space-y-6 print:space-y-4">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start print:hidden">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Network Report
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">
            A snapshot of the network data currently loaded in this report.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => window.print()}>
            <Printer /> Print report
          </Button>
          <Button variant="outline" onClick={() => exportReport("devices")}>
            <Download /> Devices CSV
          </Button>
          <Button variant="outline" onClick={() => exportReport("alerts")}>
            <Download /> Alerts CSV
          </Button>
          <Button variant="outline" onClick={() => exportReport("dns")}>
            <Download /> DNS CSV
          </Button>
        </div>
      </div>
      <p className="text-muted-foreground text-xs" role="status">
        {exported}
      </p>
      <div className="hidden print:block">
        <h1 className="text-2xl font-semibold">Network Report</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Generated from the data currently loaded in NetWatch.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Devices</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold">{data.devices.length}</p>
            <p className="text-muted-foreground text-xs">
              Loaded device records
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Alerts</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold">{data.alerts.length}</p>
            <p className="text-muted-foreground text-xs">
              {data.alerts.filter((alert) => !alert.resolved).length} unresolved
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">DNS activity</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold">{data.dnsActivity.length}</p>
            <p className="text-muted-foreground text-xs">
              Metadata records loaded
            </p>
          </CardContent>
        </Card>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Device coverage</CardTitle>
          </CardHeader>
          <CardContent>
            {data.devices.length ? (
              <div className="space-y-2 text-sm">
                {data.devices.slice(0, 8).map((device) => (
                  <div className="flex justify-between gap-3" key={device.id}>
                    <span className="truncate">
                      {deviceDisplayName(device)}
                    </span>
                    <Badge
                      variant={
                        device.status === "online" ? "success" : "secondary"
                      }
                    >
                      {device.status}
                    </Badge>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-sm">
                No devices are currently loaded.
              </p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Alert posture</CardTitle>
          </CardHeader>
          <CardContent>
            {data.alerts.length ? (
              <div className="space-y-2 text-sm">
                {data.alerts.slice(0, 8).map((alert) => (
                  <div className="flex justify-between gap-3" key={alert.id}>
                    <span className="truncate">{alert.title}</span>
                    <Badge
                      variant={
                        alert.resolved
                          ? "success"
                          : alert.severity === "high"
                            ? "warning"
                            : "secondary"
                      }
                    >
                      {alert.resolved
                        ? "Resolved"
                        : alert.severity.toUpperCase()}
                    </Badge>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-sm">
                No alerts are currently loaded.
              </p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">DNS visibility</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm">
              {data.dnsAvailable
                ? `${data.dnsActivity.length} DNS metadata records are available.`
                : "DNS activity is unavailable."}
            </p>
            <p className="text-muted-foreground mt-2 text-xs">
              NetWatch reports DNS metadata only. It does not expose encrypted
              traffic contents, full URLs, or payloads.
            </p>
          </CardContent>
        </Card>
      </div>
      <p className="text-muted-foreground text-xs">
        Privacy note: report data reflects what the configured providers expose.
        HTTPS encryption and provider configuration can limit attribution and
        visibility; no traffic contents are inferred.
      </p>
    </div>
  );
}
