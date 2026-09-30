import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div className="bg-background min-h-dvh" aria-busy="true">
      <aside
        className="border-border bg-card fixed inset-y-0 start-0 hidden w-60 border-e lg:block"
        aria-hidden="true"
      >
        <div className="border-border flex h-16 items-center gap-3 border-b px-5">
          <Skeleton className="size-8 rounded-lg" />
          <div className="space-y-1.5">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-2 w-28" />
          </div>
        </div>
        <div className="space-y-3 p-4">
          {Array.from({ length: 10 }).map((_, index) => (
            <Skeleton key={index} className="h-9" />
          ))}
        </div>
      </aside>
      <div className="lg:ps-60">
        <header className="border-border flex h-16 items-center border-b px-4 md:px-6">
          <Skeleton className="h-4 w-32" />
        </header>
        <main
          id="main-content"
          className="mx-auto w-full max-w-[1600px] space-y-6 p-4 md:p-6 lg:p-8"
          aria-live="polite"
          role="status"
        >
          <span className="sr-only">Loading network data</span>
          <Skeleton className="h-8 w-56" />
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-36" />
            ))}
          </div>
          <Skeleton className="h-80" />
        </main>
      </div>
    </div>
  );
}
