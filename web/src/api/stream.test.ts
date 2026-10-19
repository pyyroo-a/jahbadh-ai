import { afterEach, describe, expect, it, vi } from "vitest";
import { openStream } from "./stream";

class FakeSource {
  static CLOSED = 2;
  static last: FakeSource;
  readyState = 0;
  onerror: (() => void) | null = null;
  listeners: Record<string, (e: unknown) => void> = {};
  closed = false;
  url: string;
  constructor(url: string) { this.url = url; FakeSource.last = this; }
  addEventListener(kind: string, fn: (e: unknown) => void) { this.listeners[kind] = fn; }
  close() { this.closed = true; this.readyState = FakeSource.CLOSED; }
}

describe("openStream", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("tells a blip from a stream the browser has given up on", () => {
    vi.stubGlobal("EventSource", FakeSource);
    const onDrop = vi.fn(), onGone = vi.fn();
    openStream("/api/live/x/stream", () => {}, onDrop, onGone);
    FakeSource.last.readyState = 0;                // CONNECTING: the browser will retry by itself
    FakeSource.last.onerror?.();
    expect(onDrop).toHaveBeenCalledTimes(1);
    expect(onGone).not.toHaveBeenCalled();
    FakeSource.last.readyState = FakeSource.CLOSED; // a 404 after a restart: no more retries
    FakeSource.last.onerror?.();
    expect(onGone).toHaveBeenCalledTimes(1);
  });

  it("reads each message and closes itself after the end", () => {
    vi.stubGlobal("EventSource", FakeSource);
    const seen: unknown[] = [];
    openStream("/api/replay/m/stream", (m) => seen.push(m));
    FakeSource.last.listeners.end({ lastEventId: "7", data: '{"reason":"full_time"}' });
    expect(seen).toEqual([{ id: 7, kind: "end", data: { reason: "full_time" } }]);
    expect(FakeSource.last.closed).toBe(true);
  });
});
