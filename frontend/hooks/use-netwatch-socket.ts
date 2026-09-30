"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { getRuntimeConfig } from "@/lib/config";

export type SocketStatus =
  "connecting" | "connected" | "reconnecting" | "offline";

export function reconnectDelay(attempt: number): number {
  return Math.min(1_000 * 2 ** Math.max(0, attempt), 30_000);
}

export function useNetWatchSocket() {
  const router = useRouter();
  const [status, setStatus] = useState<SocketStatus>("connecting");
  const [lastEvent, setLastEvent] = useState<string | null>(null);
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let heartbeat: ReturnType<typeof setInterval> | null = null;
    let attempt = 0;
    let stopped = false;

    function scheduleReconnect() {
      if (stopped || reconnectTimer) return;
      setStatus(navigator.onLine ? "reconnecting" : "offline");
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        void connect();
      }, reconnectDelay(attempt++));
    }

    async function connect() {
      if (stopped) return;
      setStatus(attempt ? "reconnecting" : "connecting");
      try {
        const { websocketUrl } = await getRuntimeConfig();
        const parsedUrl = new URL(websocketUrl);
        if (parsedUrl.protocol !== "ws:" && parsedUrl.protocol !== "wss:") {
          throw new Error("WebSocket URL must use ws:// or wss://.");
        }
        if (stopped) return;
        socket = new WebSocket(parsedUrl.toString());
      } catch {
        scheduleReconnect();
        return;
      }
      socket.addEventListener("open", () => {
        attempt = 0;
        setStatus("connected");
        heartbeat = setInterval(() => {
          if (socket?.readyState === WebSocket.OPEN) socket.send("ping");
        }, 25_000);
      });
      socket.addEventListener("message", (message) => {
        try {
          const payload = JSON.parse(String(message.data)) as {
            event?: string;
          };
          if (!payload.event || payload.event === "system.ready") return;
          setLastEvent(payload.event);
          if (refreshTimer.current) clearTimeout(refreshTimer.current);
          refreshTimer.current = setTimeout(() => router.refresh(), 250);
        } catch {
          // Ignore malformed server messages and keep the connection alive.
        }
      });
      socket.addEventListener("close", () => {
        if (heartbeat) clearInterval(heartbeat);
        if (stopped) return;
        scheduleReconnect();
      });
      socket.addEventListener("error", () => socket?.close());
    }

    connect();
    return () => {
      stopped = true;
      socket?.close();
      if (heartbeat) clearInterval(heartbeat);
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
    };
  }, [router]);

  return { status, lastEvent };
}
