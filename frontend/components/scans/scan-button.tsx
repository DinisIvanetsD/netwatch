"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LoaderCircle, ScanLine } from "lucide-react";

import { Button } from "@/components/ui/button";
import { getScan, startScan } from "@/lib/api";

const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);

function delay(milliseconds: number) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

export function ScanButton() {
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  async function handleScan() {
    setScanning(true);
    setError(null);
    try {
      let scan = await startScan();
      for (
        let attempt = 0;
        attempt < 240 && !TERMINAL_STATUSES.has(scan.status);
        attempt += 1
      ) {
        await delay(500);
        scan = await getScan(scan.id);
      }
      if (scan.status !== "completed") {
        throw new Error(scan.error ?? "The network scan did not complete.");
      }
      router.refresh();
    } catch (scanError) {
      setError(
        scanError instanceof Error ? scanError.message : "Network scan failed.",
      );
    } finally {
      setScanning(false);
    }
  }

  return (
    <div className="flex items-center gap-2">
      <Button
        size="sm"
        onClick={handleScan}
        disabled={scanning}
        title={error ?? undefined}
      >
        {scanning ? <LoaderCircle className="animate-spin" /> : <ScanLine />}
        <span className="hidden sm:inline">
          {scanning ? "Scanning…" : error ? "Try Scan Again" : "Scan Network"}
        </span>
      </Button>
      <span className="sr-only" aria-live="polite">
        {scanning
          ? "Network scan in progress"
          : error
            ? `Network scan failed: ${error}`
            : ""}
      </span>
    </div>
  );
}
