"use client";

import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function ErrorPage({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="bg-background grid min-h-dvh place-items-center p-6">
      <Card className="w-full max-w-lg">
        <CardContent className="p-8 text-center">
          <AlertTriangle
            className="mx-auto size-6 text-amber-300"
            aria-hidden="true"
          />
          <h1 className="mt-4 text-lg font-semibold">
            NetWatch could not load this view
          </h1>
          <p className="text-muted-foreground mt-2 text-sm leading-6">
            The detailed error was kept out of the interface. Try loading the
            page again.
          </p>
          <Button className="mt-6" onClick={reset}>
            Try Again
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
