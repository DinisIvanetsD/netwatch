import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { reconnectDelay, useNetWatchSocket } from "@/hooks/use-netwatch-socket";

const router = { refresh: vi.fn() };

vi.mock("next/navigation", () => ({ useRouter: () => router }));

class FakeWebSocket extends EventTarget {
  static OPEN = 1;
  static instances: FakeWebSocket[] = [];
  readyState = FakeWebSocket.OPEN;
  constructor(public url: string) {
    super();
    FakeWebSocket.instances.push(this);
  }
  send() {}
  close() {
    this.dispatchEvent(new Event("close"));
  }
}

describe("NetWatch WebSocket", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeWebSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeWebSocket);
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("uses capped exponential reconnect delays", () => {
    expect(reconnectDelay(0)).toBe(1_000);
    expect(reconnectDelay(10)).toBe(30_000);
  });

  it("reconnects after the socket closes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            apiUrl: "http://127.0.0.1:8000",
            websocketUrl: "ws://127.0.0.1:8000/ws",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    const { unmount } = renderHook(() => useNetWatchSocket());
    await act(async () => {
      await Promise.resolve();
    });
    expect(FakeWebSocket.instances).toHaveLength(1);
    act(() => FakeWebSocket.instances[0].dispatchEvent(new Event("close")));
    await act(async () => {
      vi.advanceTimersByTime(1_000);
      await Promise.resolve();
    });
    expect(FakeWebSocket.instances).toHaveLength(2);
    unmount();
  });
});
