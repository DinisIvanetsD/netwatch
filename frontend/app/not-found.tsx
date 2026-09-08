import Link from "next/link";
import { Radar } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main className="bg-background grid min-h-dvh place-items-center p-6 text-center">
      <div>
        <Radar
          className="text-muted-foreground mx-auto size-8"
          aria-hidden="true"
        />
        <p className="text-primary mt-5 font-mono text-xs">404</p>
        <h1 className="mt-2 text-xl font-semibold">Page not found</h1>
        <p className="text-muted-foreground mt-2 text-sm">
          The requested NetWatch view does not exist.
        </p>
        <Button asChild className="mt-6">
          <Link href="/dashboard">Return to Overview</Link>
        </Button>
      </div>
    </main>
  );
}
