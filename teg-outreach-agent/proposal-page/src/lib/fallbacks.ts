import type { Proposal } from "./types";

const SECTION_LABELS: Record<string, string> = {
  priorities: "See the opportunity",
  charts: "Explore the fit",
  investment: "Review options",
};

export const heroHeadline = (p: Proposal): string =>
  p.hero_headline?.trim() || `Could Tech Expo Gujarat become a growth channel for ${p.company}?`;

export const heroSubline = (p: Proposal): string =>
  p.hero_subline?.trim() || `Evaluating whether Tech Expo Gujarat 2026 could support ${p.company}'s business development objectives.`;

export const sectionCta = (p: Proposal, key: string): string =>
  p.section_ctas?.[key]?.trim() || SECTION_LABELS[key] || "Learn more";

export const closingHeadline = (p: Proposal): string =>
  p.closing_cta_headline?.trim() || `Should we explore this opportunity further?`;

export const closingBody = (p: Proposal): string =>
  p.closing_cta_body?.trim() ||
  "Reply in the chat to discuss whether this aligns with your growth goals, or reach the team directly.";
