/**
 * Fetch-based SSE client for the Alpha AI realtime stream.
 *
 * Why not `EventSource`: it cannot send an `Authorization: Bearer` header, so
 * the JWT would have to ride in a query param and leak into proxy / access
 * logs. A `fetch` + `ReadableStream` reader attaches the same bearer header
 * as every other call, stays on the relative `/api/backend/...` rewrite (no
 * CORS, backend URL never reaches the browser), and lets us own reconnect
 * behaviour (capped exponential backoff) instead of EventSource's fixed
 * retry. The server keeps every connection alive with `: ping` comments
 * (see backend `app/api/routes/realtime.py`), so a stalled stream surfaces
 * as a reader error and triggers the same reconnect path.
 */

export interface RealtimeEvent {
  type: string;
  payload: Record<string, unknown>;
}

export interface StreamHandlers {
  onEvent: (event: RealtimeEvent) => void;
  onOpen?: () => void;
  /** Called when the stream drops or the request fails; reconnect is ours. */
  onClose?: (reason: "error" | "done") => void;
}

/** Parse one SSE frame (`event:` + `data:` lines) into a RealtimeEvent. */
export function parseSseFrame(frame: string): RealtimeEvent | null {
  let type = "message";
  const dataLines: string[] = [];
  for (const rawLine of frame.split("\n")) {
    const line = rawLine.replace(/\r$/, "");
    if (line.startsWith(":")) continue; // comment / keepalive
    if (line.startsWith("event:")) type = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (dataLines.length === 0) return null;
  try {
    const payload = JSON.parse(dataLines.join("\n")) as Record<string, unknown>;
    return { type, payload };
  } catch {
    return null; // malformed payload — drop the frame, keep streaming
  }
}

/**
 * Consume `/api/backend/realtime/stream` until `signal` is aborted.
 * Resolves when the loop exits; never throws (errors go to `onClose`).
 */
export async function consumeRealtimeStream(
  signal: AbortSignal,
  handlers: StreamHandlers,
  fetchImpl: typeof fetch = fetch,
): Promise<void> {
  try {
    const response = await fetchImpl("/api/backend/realtime/stream", {
      method: "GET",
      headers: { Accept: "text/event-stream" },
      cache: "no-store",
      signal,
    });
    if (!response.ok || !response.body) {
      handlers.onClose?.("error");
      return;
    }
    handlers.onOpen?.();

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      // Frames are separated by a blank line; keep any partial tail buffered.
      for (;;) {
        const boundary = buffer.indexOf("\n\n");
        if (boundary === -1) break;
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const event = parseSseFrame(frame);
        if (event) handlers.onEvent(event);
      }
    }
    handlers.onClose?.("done");
  } catch {
    // AbortError lands here too — callers decide whether to reconnect.
    handlers.onClose?.("error");
  }
}

/** Backoff for stream reconnects: 1s → 2s → 4s → … capped at 15s. */
export function reconnectDelayMs(attempt: number): number {
  return Math.min(1_000 * 2 ** attempt, 15_000);
}
