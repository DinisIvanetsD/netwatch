import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import "./globals.css";

const geistSans = Geist({
  subsets: ["latin"],
  variable: "--font-geist-sans",
  display: "swap",
});

const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-geist-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "NetWatch",
    template: "%s · NetWatch",
  },
  description: "Know what is on your network.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`dark ${geistSans.variable} ${geistMono.variable}`}
    >
      <body className={`${geistSans.className} min-h-dvh antialiased`}>
        <a
          href="#main-content"
          className="focus:bg-primary focus:text-primary-foreground fixed start-3 top-3 z-[100] -translate-y-20 rounded-md px-3 py-2 text-sm font-medium transition-transform focus:translate-y-0"
        >
          Skip to main content
        </a>
        {children}
      </body>
    </html>
  );
}
