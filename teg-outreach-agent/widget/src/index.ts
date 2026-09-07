import { ChatSocket, submitInquiry, type InquiryInput } from "./api.ts";
import { renderChat, renderForm } from "./ui.ts";

export function mount(
  el: HTMLElement,
  opts: { apiBaseUrl: string; wsBaseUrl: string },
): void {
  renderForm(el, async (input: InquiryInput) => {
    el.textContent = "";
    const status = document.createElement("div");
    status.textContent = "Preparing your session…";
    el.appendChild(status);

    let res;
    try {
      res = await submitInquiry(opts.apiBaseUrl, input);
    } catch {
      status.textContent = "Something went wrong. Please try again.";
      return;
    }

    el.textContent = "";
    const chat = renderChat(el);
    chat.addMessage("agent", res.opening_message);

    const sock = new ChatSocket(opts.wsBaseUrl, res.session_id);
    sock.onEvent((ev) => {
      if (ev.type === "reply" && ev.text) {
        chat.addMessage("agent", ev.text);
        if (ev.cta_status) chat.setStatus(`Status: ${ev.cta_status}`);
      } else if (ev.type === "handoff") {
        chat.setStatus("Our team will follow up with you.");
      } else if (ev.type === "proposal_pending") {
        chat.showProposalPending((ev as { company?: string }).company);
      } else if (ev.type === "attachment") {
        chat.showProposalLink(ev as never);
      } else if (ev.type === "proposal_failed") {
        chat.showProposalFailed();
      } else if (ev.type === "turn_failed") {
        chat.addMessage(
          "agent",
          "Sorry — I lost that one. Could you send it again?",
        );
      }
    });
    chat.onSend((text) => {
      chat.addMessage("you", text);
      sock.send(text);
    });
  });
}

const auto =
  typeof document !== "undefined" ? document.getElementById?.("teg-outreach") : null;
if (auto) {
  const el = auto as HTMLElement;
  mount(el, {
    apiBaseUrl: el.getAttribute("data-api") || "",
    wsBaseUrl: el.getAttribute("data-ws") || "",
  });
}
