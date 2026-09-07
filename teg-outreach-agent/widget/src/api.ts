export interface InquiryInput {
  person_name: string;
  company_name: string;
  email?: string;
  phone?: string;
  message?: string;
  participation_type?: string;
  consent?: boolean;
}

export interface InquiryResponse {
  session_id: string;
  opening_message: string;
  persona: string;
}

export type ChatEvent = {
  type:
    | "opening"
    | "reply"
    | "handoff"
    | "proposal_pending"
    | "attachment"
    | "proposal_failed"
    | "turn_failed";
  text?: string;
  cta_status?: string;
  should_handoff?: boolean;
  company?: string;
  kind?: string;
  proposal_id?: string;
  version?: number;
  filename?: string;
  bytes?: number;
  pdf_url?: string;
  png_url?: string;
};

export async function submitInquiry(
  baseUrl: string,
  input: InquiryInput,
): Promise<InquiryResponse> {
  const resp = await fetch(`${baseUrl}/inquiries`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (resp.status !== 202) {
    throw new Error(`inquiry failed: ${resp.status}`);
  }
  return (await resp.json()) as InquiryResponse;
}

export class ChatSocket {
  private ws: WebSocket;
  private cb: ((e: ChatEvent) => void) | null = null;

  constructor(wsUrl: string, sessionId: string) {
    this.ws = new WebSocket(`${wsUrl}/chat/${sessionId}`);
    this.ws.onmessage = (ev: MessageEvent) => {
      if (this.cb) this.cb(JSON.parse(ev.data) as ChatEvent);
    };
  }

  onEvent(cb: (e: ChatEvent) => void): void {
    this.cb = cb;
  }

  send(text: string): void {
    this.ws.send(JSON.stringify({ type: "message", text }));
  }

  end(): void {
    this.ws.send(JSON.stringify({ type: "end" }));
  }

  close(): void {
    this.ws.close();
  }
}
