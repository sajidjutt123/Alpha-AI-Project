/**
 * Unit tests for the SSE client logic (Phase 9): frame parsing, stream
 * consumption with a fake transport, and reconnect backoff.
 */

import { describe, expect, it } from "vitest";

import {
  consumeRealtimeStream,
  parseSseFrame,
  reconnectDelayMs,
} from "@/lib/realtime";

import type { RealtimeEvent } from "@/lib/realtime";

function sse(...frames: string[]) {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const frame of frames) controller.enqueue(encoder.encode(frame));
      controller.close();
    },
  });
}

describe("parseSseFrame", () => {
  it("parses event + data lines", () => {
    const event = parseSseFrame('event: lead.created\ndata: {"lead_id": "x"}');
    expect(event).toEqual({
      type: "lead.created",
      payload: { lead_id: "x" },
    });
  });

  it("joins multiline data payloads", () => {
    const event = parseSseFrame('data: {"a":\ndata: 1}');
    expect(event).toEqual({ type: "message", payload: { a: 1 } });
  });

  it("ignores comment frames (keepalives)", () => {
    expect(parseSseFrame(": ping")).toBeNull();
    expect(parseSseFrame(": connected")).toBeNull();
  });

  it("drops malformed JSON without throwing", () => {
    expect(parseSseFrame("event: x\ndata: not-json")).toBeNull();
  });

  it("defaults the event type to message", () => {
    const event = parseSseFrame('data: {"ok": true}');
    expect(event?.type).toBe("message");
  });
});

describe("consumeRealtimeStream", () => {
  function fakeFetch(body: ReadableStream<Uint8Array> | null, ok = true) {
    return async () =>
      new Response(body, { status: ok ? 200 : 500, headers: { "Content-Type": "text/event-stream" } });
  }

  it("delivers complete frames and ignores keepalive comments", async () => {
    const events: RealtimeEvent[] = [];
    await consumeRealtimeStream(new AbortController().signal, {
      onEvent: (event) => events.push(event),
    }, fakeFetch(sse(": connected\n\n", 'event: lead.updated\ndata: {"lead_id":"a"}\n\n', ": ping\n\n")));

    expect(events).toEqual([{ type: "lead.updated", payload: { lead_id: "a" } }]);
  });

  it("buffers partial frames across chunk boundaries", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('event: message.created\nda'));
        controller.enqueue(encoder.encode('ta: {"preview":"hi"}\n'));
        controller.enqueue(encoder.encode("\n"));
        controller.close();
      },
    });
    const events: RealtimeEvent[] = [];
    await consumeRealtimeStream(
      new AbortController().signal,
      { onEvent: (event) => events.push(event) },
      fakeFetch(stream),
    );
    expect(events).toEqual([
      { type: "message.created", payload: { preview: "hi" } },
    ]);
  });

  it("reports onClose(error) for non-2xx without events", async () => {
    const closings: string[] = [];
    await consumeRealtimeStream(
      new AbortController().signal,
      { onEvent: () => void 0, onClose: (reason) => closings.push(reason) },
      fakeFetch(null, false),
    );
    expect(closings).toEqual(["error"]);
  });

  it("reports onClose(done) when the server ends the stream", async () => {
    const closings: string[] = [];
    await consumeRealtimeStream(
      new AbortController().signal,
      { onEvent: () => void 0, onClose: (reason) => closings.push(reason) },
      fakeFetch(sse()),
    );
    expect(closings).toEqual(["done"]);
  });

  it("treats an aborted request as an error close (never throws)", async () => {
    const controller = new AbortController();
    controller.abort();
    const closings: string[] = [];
    await expect(
      consumeRealtimeStream(
        controller.signal,
        { onEvent: () => void 0, onClose: (reason) => closings.push(reason) },
        async () => {
          throw new DOMException("aborted", "AbortError");
        },
      ),
    ).resolves.toBeUndefined();
    expect(closings).toEqual(["error"]);
  });
});

describe("reconnectDelayMs", () => {
  it("grows exponentially and caps at 15s", () => {
    expect(reconnectDelayMs(0)).toBe(1_000);
    expect(reconnectDelayMs(1)).toBe(2_000);
    expect(reconnectDelayMs(3)).toBe(8_000);
    expect(reconnectDelayMs(5)).toBe(15_000);
    expect(reconnectDelayMs(20)).toBe(15_000);
  });
});
