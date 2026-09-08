"use client";

export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en" className="dark">
      <body className="grid min-h-dvh place-items-center bg-[#111318] p-6 text-[#f2f4f7]">
        <main className="max-w-md text-center">
          <h1 className="text-xl font-semibold">
            NetWatch encountered an unexpected error
          </h1>
          <p className="mt-2 text-sm text-[#9ca3af]">
            Reload the application to continue.
          </p>
          <button
            className="mt-6 rounded-md bg-[#73b6ef] px-4 py-2 text-sm font-medium text-[#101820]"
            onClick={reset}
          >
            Reload
          </button>
        </main>
      </body>
    </html>
  );
}
