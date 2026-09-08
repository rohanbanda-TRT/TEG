// src/api.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { submitInquiry, ChatSocket } from "./api.ts";

test("submitInquiry posts and parses", async () => {
  const calls: any[] = [];
  globalThis.fetch = (async (url: string, init: any) => {
    calls.push({ url, init });
    return {
      status: 202,
      json: async () => ({ session_id: "s1", opening_message: "hi", persona: "visitor" }),
    };
  }) as any;

  const res = await submitInquiry("http://api", { person_name: "Rohan B", company_name: "TRT" });
  assert.equal(res.session_id, "s1");
  assert.equal(calls[0].url, "http://api/inquiries");
  assert.equal(JSON.parse(calls[0].init.body).company_name, "TRT");
});

test("submitInquiry throws on non-202", async () => {
  globalThis.fetch = (async () => ({ status: 422, json: async () => ({}) })) as any;
  await assert.rejects(() =>
    submitInquiry("http://api", { person_name: "x", company_name: "y" })
  );
});

test("ChatSocket wires url and forwards events", () => {
  const sent: string[] = [];
  let handler: ((e: any) => void) | null = null;
  class FakeWS {
    onmessage: ((e: any) => void) | null = null;
    onopen: (() => void) | null = null;
    constructor(public url: string) {}
    send(s: string) { sent.push(s); }
    close() {}
  }
  (globalThis as any).WebSocket = FakeWS;

  const cs = new ChatSocket("ws://api", "s1");
  cs.onEvent((e) => { handler = () => {}; assert.equal(e.type, "reply"); });
  const raw: any = (cs as any).ws;
  assert.equal(raw.url, "ws://api/chat/s1");
  raw.onmessage({ data: JSON.stringify({ type: "reply", text: "ok", cta_status: "offered" }) });
  cs.send("hello");
  assert.equal(JSON.parse(sent[0]).text, "hello");
});
