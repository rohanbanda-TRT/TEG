import type { Payload } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export async function fetchProposal(id: string): Promise<Payload> {
  const res = await fetch(`${API_BASE}/proposals/${id}.json`);
  if (!res.ok) throw new Error(`proposal ${id}: ${res.status}`);
  return (await res.json()) as Payload;
}
