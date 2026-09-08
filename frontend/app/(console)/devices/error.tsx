"use client";

import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function DevicesError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <Card>
      <CardContent className="flex min-h-72 flex-col items-center justify-center p-8 text-center">
        <AlertTriangle className="size-6 text-amber-300" aria-hidden="true" />
        <h1 className="mt-4 text-lg font-semibold">
          Device inventory is unavailable
        </h1>
        <p className="text-muted-foreground mt-2 max-w-md text-sm leading-6">
          NetWatch could not reach the backend API. Confirm the backend is
          running and try again.
        </p>
        <Button className="mt-6" onClick={reset}>
          Try Again
        </Button>
      </CardContent>
    </Card>
  );
}
