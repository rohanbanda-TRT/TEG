import { test } from "node:test";
import assert from "node:assert/strict";

// minimal DOM shim
class El {
  children: El[] = [];
  attrs: Record<string, string> = {};
  listeners: Record<string, ((e: any) => void)[]> = {};
  value = "";
  checked = false;
  textContent = "";
  tagName: string;
  constructor(tag: string) {
    this.tagName = tag.toUpperCase();
  }
  appendChild(c: El) {
    this.children.push(c);
    return c;
  }
  removeChild(c: El) {
    this.children = this.children.filter((x) => x !== c);
    return c;
  }
  setAttribute(k: string, v: string) {
    this.attrs[k] = v;
  }
  getAttribute(k: string) {
    return this.attrs[k] ?? null;
  }
  addEventListener(k: string, cb: (e: any) => void) {
    (this.listeners[k] ||= []).push(cb);
  }
  querySelector(sel: string): El | null {
    const want = sel.replace(/[#.\[\]]/g, "").replace(/^name=/, "").replace(/^role=/, "");
    const walk = (n: El): El | null => {
      if (
        n.attrs.name === want ||
        n.attrs.id === want ||
        n.attrs.role === want ||
        n.tagName === sel.toUpperCase()
      )
        return n;
      for (const c of n.children) {
        const r = walk(c);
        if (r) return r;
      }
      return null;
    };
    return walk(this);
  }
  fire(k: string, e: any = { preventDefault() {} }) {
    (this.listeners[k] || []).forEach((f) => f(e));
  }
}
(globalThis as any).document = {
  createElement: (t: string) => new El(t),
};

const { renderForm, renderChat } = await import("./ui.ts");

test("renderForm calls onSubmit with required fields", () => {
  const root = new El("div") as any;
  let got: any = null;
  renderForm(root, (input) => {
    got = input;
  });
  root.querySelector("[name=person_name]").value = "Rohan B";
  root.querySelector("[name=company_name]").value = "TRT";
  root.querySelector("form").fire("submit");
  assert.equal(got.person_name, "Rohan B");
  assert.equal(got.company_name, "TRT");
});

test("renderForm blocks submit when company missing", () => {
  const root = new El("div") as any;
  let calls = 0;
  renderForm(root, () => {
    calls++;
  });
  root.querySelector("[name=person_name]").value = "Rohan B";
  root.querySelector("form").fire("submit");
  assert.equal(calls, 0);
});

test("renderChat addMessage and aria-live log", () => {
  const root = new El("div") as any;
  const chat = renderChat(root);
  chat.addMessage("agent", "hello");
  const log = root.querySelector("[role=log]") ?? root.querySelector("log");
  assert.ok(log);
  assert.equal(log.getAttribute("aria-live"), "polite");
});

test("renderChat onSend fires with input value", () => {
  const root = new El("div") as any;
  const chat = renderChat(root);
  let sent = "";
  chat.onSend((t) => {
    sent = t;
  });
  root.querySelector("[name=chat_input]").value = "how much is a stall?";
  root.querySelector("[name=chat_send]").fire("click");
  assert.equal(sent, "how much is a stall?");
});

import { humanSize } from "./ui.ts";

test("humanSize formats", () => {
  assert.equal(humanSize(900), "900 B");
  assert.equal(humanSize(148213), "145 KB");
});

test("renderChat shows attachment card with links", () => {
  const root = new El("div") as any;
  const chat = renderChat(root);
  chat.showAttachment({
    kind: "proposal",
    proposal_id: "p1",
    version: 2,
    filename: "TEG-2026-Proposal-Acme-v2.pdf",
    bytes: 148213,
    pdf_url: "/proposals/p1.pdf",
    png_url: "/proposals/p1/preview.png",
  });
  assert.ok(JSON.stringify(root).includes("/proposals/p1.pdf"));
  assert.ok(JSON.stringify(root).includes("data-attachment"));
});

test("renderChat pending then attachment replaces skeleton", () => {
  const root = new El("div") as any;
  const chat = renderChat(root);
  chat.showProposalPending("Acme");
  chat.showAttachment({
    kind: "proposal",
    proposal_id: "p1",
    version: 1,
    filename: "f.pdf",
    bytes: 1000,
    pdf_url: "/proposals/p1.pdf",
    png_url: "/x.png",
  });
  const cards = JSON.stringify(root).match(/data-attachment/g) || [];
  assert.equal(cards.length, 1);
});

test("renderProposalLink shows title, blurb, open + pdf links", () => {
  const root = new El("div") as any;
  const chat = renderChat(root);
  chat.showProposalLink({
    kind: "proposal_link",
    proposal_id: "p1",
    version: 1,
    page_url: "/p/p1",
    pdf_url: "/proposals/p1.pdf",
    title: "Your TEG 2026 proposal for Acme",
    blurb: "Three focused days from cold outreach to booked meetings.",
  });
  const s = JSON.stringify(root);
  assert.ok(s.includes("/p/p1"));
  assert.ok(s.includes("/proposals/p1.pdf"));
  assert.ok(s.includes("Your TEG 2026 proposal for Acme"));
  assert.ok(s.includes("data-attachment"));
});

test("pending then proposal_link replaces skeleton", () => {
  const root = new El("div") as any;
  const chat = renderChat(root);
  chat.showProposalPending("Acme");
  chat.showProposalLink({
    kind: "proposal_link", proposal_id: "p1", version: 1,
    page_url: "/p/p1", pdf_url: "/proposals/p1.pdf", title: "t", blurb: "b",
  });
  const cards = JSON.stringify(root).match(/data-attachment/g) || [];
  assert.equal(cards.length, 1);
});
