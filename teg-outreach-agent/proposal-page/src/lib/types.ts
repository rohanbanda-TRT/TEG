export interface SectorFitRow {
  lever: string;
  weight: number;
}

export interface Pain {
  pain: string;
  teg_answer: string;
}

export interface JourneyStage {
  stage: string; // today | growth_move | barrier | teg_opportunity | action | potential
  title: string;
  points: string[];
}

export interface Package {
  name: string;
  price_line: string;
  includes: string[];
  payment_plan: string;
}

export interface Proposal {
  company: string;
  person: string;
  person_role?: string | null;
  sector?: string | null;
  persona: string;
  hero_headline?: string;
  hero_subline?: string;
  executive_summary: string;
  pains: Pain[];
  sector_fit: SectorFitRow[];
  growth_journey?: JourneyStage[];
  proof: string[];
  peer_companies: string[];
  peers_in_sector_total?: number;
  peer_context_line?: string;
  scale_note?: string;
  target_industries?: string[];
  target_industries_note?: string;
  how_a_teg_plays_out: string[];
  roi_framing: string;
  recommended_package: Package;
  section_ctas?: Record<string, string>;
  closing_cta_headline?: string;
  closing_cta_body?: string;
  next_steps: string[];
  contact: string;
}

export interface Payload {
  id: string;
  version: number;
  generated_on: string | null;
  // Present only for proposals rendered before the link-only delivery path —
  // the page itself is the deliverable now, so this is never shown in the UI.
  pdf_url?: string | null;
  proposal: Proposal;
}
