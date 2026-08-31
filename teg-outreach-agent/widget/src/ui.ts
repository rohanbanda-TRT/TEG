import type { InquiryInput } from "./api.ts";

function h(tag: string, attrs: Record<string, string> = {}, text = ""): HTMLElement {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (text) el.textContent = text;
  return el;
}

export function renderForm(
  root: HTMLElement,
  onSubmit: (input: InquiryInput) => void,
): void {
  const form = h("form");
  const mk = (name: string, type: string, ph: string, required = false) => {
    const i = h("input", { name, type, placeholder: ph });
    if (required) i.setAttribute("required", "required");
    return i;
  };
  form.appendChild(mk("person_name", "text", "Your name", true));
  form.appendChild(mk("company_name", "text", "Company name", true));
  form.appendChild(mk("email", "email", "Work email (optional)"));
  form.appendChild(mk("message", "text", "What are you interested in? (optional)"));

  const sel = h("select", { name: "participation_type" });
  for (const v of ["", "visitor", "exhibitor", "sponsor", "startup_pitch", "speaker"]) {
    sel.appendChild(h("option", { value: v }, v || "I'm not sure yet"));
  }
  form.appendChild(sel);

  const consent = h("input", { name: "consent", type: "checkbox" });
  form.appendChild(consent);
  form.appendChild(h("label", {}, "You may contact me about TEG 2026"));

  form.appendChild(h("button", { type: "submit" }, "Start"));

  form.addEventListener("submit", (e: Event) => {
    e.preventDefault();
    const val = (n: string) =>
      (form.querySelector(`[name=${n}]`) as HTMLInputElement | null)?.value?.trim() || "";
    const person = val("person_name");
    const company = val("company_name");
    if (!person || !company) return;
    onSubmit({
      person_name: person,
      company_name: company,
      email: val("email") || undefined,
      message: val("message") || undefined,
      participation_type: val("participation_type") || undefined,
      consent: (form.querySelector("[name=consent]") as HTMLInputElement | null)?.checked,
    });
  });

  root.appendChild(form);
}

export function renderChat(root: HTMLElement): {
  addMessage: (role: "agent" | "you", text: string) => void;
  setStatus: (s: string) => void;
  onSend: (cb: (text: string) => void) => void;
} {
  const wrap = h("div", { class: "teg-chat" });
  const log = h("div", { role: "log", "aria-live": "polite", class: "teg-log" });
  const status = h("div", { class: "teg-status" });
  const input = h("input", { name: "chat_input", type: "text", placeholder: "Type a message" });
  const send = h("button", { name: "chat_send", type: "button" }, "Send");

  wrap.appendChild(log);
  wrap.appendChild(status);
  wrap.appendChild(input);
  wrap.appendChild(send);
  root.appendChild(wrap);

  let sendCb: ((t: string) => void) | null = null;
  send.addEventListener("click", () => {
    const v = (input as HTMLInputElement).value.trim();
    if (v && sendCb) {
      sendCb(v);
      (input as HTMLInputElement).value = "";
    }
  });

  return {
    addMessage(role, text) {
      log.appendChild(
        h("div", { class: `teg-msg teg-${role}` }, `${role === "agent" ? "TEG" : "You"}: ${text}`),
      );
    },
    setStatus(s) {
      status.textContent = s;
    },
    onSend(cb) {
      sendCb = cb;
    },
  };
}
