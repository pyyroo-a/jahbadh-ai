// Follows one desk stream. EventSource reconnects by itself after a blip and sends Last-Event-ID, so the
// server resumes where we left off; the reducer drops anything it has already seen.

import { STREAM_KINDS, type StreamMessage } from "./types";

export function openStream(url: string, onMessage: (m: StreamMessage) => void, onDrop?: () => void): () => void {
  const source = new EventSource(url);
  for (const kind of STREAM_KINDS) {
    source.addEventListener(kind, (e) => {
      const event = e as MessageEvent<string>;
      onMessage({ id: Number(event.lastEventId), kind, data: JSON.parse(event.data) } as StreamMessage);
      if (kind === "end") source.close();    // otherwise the browser would reconnect after full time
    });
  }
  source.onerror = () => {
    if (source.readyState !== EventSource.CLOSED) onDrop?.();
  };
  return () => source.close();
}
