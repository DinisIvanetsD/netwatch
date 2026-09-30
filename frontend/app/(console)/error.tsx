"use client";

import { AlertTriangle, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function ConsoleError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="border-border bg-card mx-auto flex min-h-[20rem] max-w-xl flex-col items-center justify-center rounded-xl border px-6 py-12 text-center">
      <AlertTriangle className="text-warning size-8" aria-hidden="true" />
      <h1 className="mt-4 text-lg font-semibold">
        NetWatch could not load this view
      </h1>
      <p className="text-muted-foreground mt-2 max-w-md text-sm">
        The local services may be starting or temporarily unavailable. Try again
        after checking that the NetWatch backend is running.
      </p>
      <Button className="mt-6" onClick={reset}>
        <RefreshCw aria-hidden="true" />
        Try again
      </Button>
    </div>
  );
}
