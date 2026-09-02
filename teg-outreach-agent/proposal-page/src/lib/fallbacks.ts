import type { Proposal } from "./types";

const SECTION_LABELS: Record<string, string> = {
  priorities: "See the plan",
  charts: "Explore the numbers",
  investment: "Get your quote",
};

export const heroHeadline = (p: Proposal): string =>
  p.hero_headline?.trim() || `A proposal for ${p.company}`;

export const heroSubline = (p: Proposal): string =>
  p.hero_subline?.trim() || (p.executive_summary.split(/(?<=\.)\s/)[0] ?? p.executive_summary);

export const sectionCta = (p: Proposal, key: string): string =>
  p.section_ctas?.[key]?.trim() || SECTION_LABELS[key] || "Learn more";

export const closingHeadline = (p: Proposal): string =>
  p.closing_cta_headline?.trim() || `Let's make TEG 2026 count for ${p.company}`;

export const closingBody = (p: Proposal): string =>
  p.closing_cta_body?.trim() ||
  "Reply in the chat, or reach the team directly — we'll take it from here.";
