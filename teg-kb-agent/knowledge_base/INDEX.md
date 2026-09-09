# Tech Expo Gujarat — Knowledge Base Index

> **Event:** Tech Expo Gujarat 2026 (TEG 2026)
> **Organizer:** AIMED TECH EXPO GUJARAT LLP
> **Website:** https://www.techexpogujarat.com/
> **Compiled:** August 2026 (re-verified August 27, 2026; TEG 2026 pricing + brochure exhibitor pass August 31, 2026; site re-check September 1, 2026 — early-bird offer changed 60% → 50%, no other factual changes; research pass September 9, 2026 — see "New findings this pass" below)
> **Sources:** Full site crawl of techexpogujarat.com + events.techexpogujarat.com + linked third-party exhibitor/press pages + official `teg-cost.pdf` and `teg-sponsors-brochure.pdf` collateral + headless-browser re-checks + MCA-derived legal filings + LinkedIn/Instagram/Facebook (Sept 9, 2026)
> **Total files:** 216 (15 topic files [incl. `pricing/pricing_and_packages.md`, `testimonials/exhibitor_testimonials.md`, `venture_capital/venture_capital_and_investors.md`, and new `competitive_landscape/adjacent_events.md`] + 6 root-level files [`exhibitor_benefits_analysis.md`, `inquiry_page_content.md`, `data_schema.md`, `sector_wise_participation.md`, `outreach_config.md`, `event_goals_and_problem.md`] + 35 individual speaker profiles + 26 organizers_team files [2 index/summary + 24 individual organizer/co-organizer profiles] + 134 exhibitors/companies files [133 individual company profiles + companies_index.md] + INDEX.md)

---

## Complete File Structure

```
teg_knowledge_base/
│
├── INDEX.md                                          ← This file — master map + quick reference
├── exhibitor_benefits_analysis.md                    ← Persona-based "why exhibit" analysis + lead qualification questions
├── inquiry_page_content.md                           ← Draft inquiry-page copy (hero, CTAs, form fields) — not site-sourced
├── data_schema.md                                    ← Proposed internal data-fields schema (event/exhibitor/speaker/ticket/lead records)
├── sector_wise_participation.md                      ← Company-level sector breakdown (TEG 2024/2026), confidence-tiered
├── event_goals_and_problem.md                        ← What TEG is FOR: goals, problem solved, mechanism, evidence, per-persona pain library
│
├── event_overview/
│   └── event_info.md                                 ← Identity, dates, scale, vision/mission, industries
│
├── venue_logistics/
│   └── venue_and_logistics.md                        ← GUCEC details, floor plan, timings, booth sizes
│
├── exhibitors/
│   ├── exhibitors_directory.md                        ← TEG 2026 named brochure exhibitor list + TEG 2024 master table (linked) + stall packages
│   └── companies/                                      ← 131 individual company profiles (83 TEG 2024 + 48 TEG 2026 brochure) + 1 index
│       └── companies_index.md                          ← Confidence-tiered index (127 Verified · 4 Medium · 2 Low)
│
├── speakers/
│   ├── speakers_and_agenda.md                         ← TEG 2024 full speaker list + schedule; TEG 2026 status
│   └── individuals/                                    ← 35 individual speaker profiles
│       ├── akshit_rao.md
│       ├── aniruddh_nagodra.md
│       ├── ankur_warikoo.md
│       ├── anil_joshi.md
│       ├── bhavin_bhagat.md
│       ├── ca_harsh_mehta.md
│       ├── chitrak_shah.md
│       ├── dharmesh_acharya.md
│       ├── dr_gnanvatsal_swami.md
│       ├── harshal_shah.md
│       ├── jaimin_shah.md
│       ├── jimit_bagadia.md
│       ├── kanaksinh_rana.md
│       ├── kaushal_mehta.md
│       ├── kiran_deshpande.md
│       ├── kishorsinh_zala.md
│       ├── mandar_mhatre.md
│       ├── mihir_joshi.md
│       ├── nachiket_patel.md
│       ├── pratiksinh_chudasama.md
│       ├── pratul_shroff.md
│       ├── ramesh_marand.md
│       ├── satyarth_srivastava.md
│       ├── savjibhai_dholakia.md
│       ├── shalin_sheth.md
│       ├── sharad_bansal.md
│       ├── shri_nagarajan_ias.md
│       ├── siddharthsinh_vaghela.md
│       ├── sonu_sharma.md
│       ├── varsha_adhikari.md
│       ├── vatsal_shah.md
│       ├── vishal_mehta.md
│       ├── vishal_virani.md
│       ├── winston_tixeira.md
│       └── yash_vasant.md
│
├── registration/
│   └── registration_and_passes.md                    ← How to register, ticket promo, pass entitlements
│
├── sponsors_partners/
│   └── sponsors_and_partners.md                      ← TEG 2026 sponsor tiers/benefits + TEG 2024 named sponsors + associate partners
│
├── venture_capital/
│   └── venture_capital_and_investors.md              ← Canonical VC roster (15 firms), investor-speakers, matchmaking track, funding figures
│
├── organizers_team/
│   ├── organizers_and_team.md                        ← Core team index (links to 12 core + 12 co-organizer profiles)
│   ├── co_organizers.md                              ← Thin index linking to 12 individual co-organizer profiles
│   ├── taral_shah.md
│   ├── harshal_shah.md
│   ├── bhavik_shah.md
│   ├── sandeep_sisodiya.md
│   ├── gurpritsingh_saini.md
│   ├── pinakin_soni.md
│   ├── tejas_shah.md
│   ├── nirav_shah.md
│   ├── nilay_khandhar.md
│   ├── tapan_patel.md
│   ├── rajan_rawal.md
│   ├── vishal_rajpurohit.md
│   ├── jigar_joshi.md
│   ├── manthan_bhavsar.md
│   ├── pruthviraj_zala.md
│   ├── parth_talaviya.md
│   ├── jainesh_shah.md
│   ├── mehul_shah.md
│   ├── divyesh_gohil.md
│   ├── krutik_patel.md
│   ├── saumil_patel.md
│   ├── upendrasinh_zala.md
│   ├── vikash_agrawal.md
│   └── rushabh_champaneri.md
│
├── past_editions/
│   └── past_editions_history.md                      ← TEG 2024 recap, testimonials, growth trajectory
│
├── related_events/
│   └── related_events.md                              ← TEG Business Retreat 2025 + TEG Ignite 2026 (full detail, + VC matchmaking)
│
├── digital_presence/
│   └── digital_channels.md                            ← Official channels, site structure, vendors, digital momentum (follower counts)
│
├── competitive_landscape/
│   └── adjacent_events.md                              ← Non-TEG-affiliated Gujarat tech expos (FITAG, EFY Expo, TECH VAPI) — market context, NOT a TEG satellite event (see related_events/ for those)
│
└── faq/
    └── faq_event.md                                   ← Official on-site FAQ
```

---

## Quick Reference

### Event Identity
| Field | Value |
|---|---|
| Organizer | AIMED TECH EXPO GUJARAT LLP |
| Dates | 27–28–29 November 2026 |
| Venue | GUCEC, Ahmedabad (60-acre campus, 7,000+ sq.m exhibition space) |
| Theme | "Beacon of Rising Tech Innovation & AI" |
| Scale target | 15,000+ visitors · 250+ exhibitors · 25+ speakers |
| Address | 301, Iscon Centre, Satellite, Ahmedabad, Gujarat – 380015 |
| Phone | +91 98989 23712 |
| Email | info@techexpogujarat.com |

### Key Links
| Purpose | URL |
|---|---|
| Main site | https://www.techexpogujarat.com/ |
| Ticketing/exhibitor portal | https://events.techexpogujarat.com/e/6946415bbc05410ef59021d7 |
| Become an exhibitor | https://www.techexpogujarat.com/become-an-exhibitor/ |
| Become a sponsor | https://www.techexpogujarat.com/become-a-sponsor/ |
| About TEG | https://www.techexpogujarat.com/about-us/ |
| TEG 2024 recap | https://www.techexpogujarat.com/tech-expo-2024/ |
| Retreat 2025 | https://www.techexpogujarat.com/retreat-2025/ |
| TEG Ignite 2026 | https://www.techexpogujarat.com/teg-ignite-2026/ |

### Growth Trajectory
| Edition | Attendees | Exhibitors | Format |
|---|---|---|---|
| TEG 2024 | 8,000+ | 125+ | 2-day public expo |
| TEG Retreat 2025 | 150+ (invite-only) | — | 2-day offsite |
| TEG Ignite 2026 | 150+ | — | 1-evening curtain-raiser |
| **TEG 2026** | **15,000+ (target)** | **250+ (target)** | **3-day public expo** |

### TRT Connection (internal note)
Tapan Patel, Co-Founder/CMO of Third Rock Techkno, sits on TEG's core organizing team, and TRT exhibited at TEG 2024. This is a direct existing relationship worth factoring into any TEG 2026 outreach, sponsorship, or exhibitor strategy for TRT. Full detail: `organizers_team/organizers_and_team.md`.

---

## File Loading Guide — By Task Type

| Task | Load These Files |
|---|---|
| **General event overview / pitch** | `event_overview/event_info.md` + `faq/faq_event.md` |
| **Deciding whether/how to exhibit** | `exhibitors/exhibitors_directory.md` + `registration/registration_and_passes.md` |
| **Personalized pitch / proposal / "why should we participate"** | `event_goals_and_problem.md` + `exhibitor_benefits_analysis.md` |
| **Sponsorship decision** | `sponsors_partners/sponsors_and_partners.md` + `pricing/pricing_and_packages.md` |
| **VC / investor / fundraising angle** | `venture_capital/venture_capital_and_investors.md` (+ `related_events/related_events.md` for matchmaking mechanics) |
| **Who's involved / relationship mapping** | `organizers_team/organizers_and_team.md` (+ individual profile files for depth on one person) |
| **Planning travel / logistics** | `venue_logistics/venue_and_logistics.md` |
| **Understanding speaker caliber / past programming** | `speakers/speakers_and_agenda.md` (+ `speakers/individuals/` for depth on one speaker) + `past_editions/past_editions_history.md` |
| **Understanding the broader TEG ecosystem (Retreat, Ignite)** | `related_events/related_events.md` |
| **PR / media / social strategy** | `digital_presence/digital_channels.md` |
| **Competitive landscape / who else is running a Gujarat tech expo** | `competitive_landscape/adjacent_events.md` |
| **Quick facts / numbers** | `INDEX.md` (this file) |

---

## Known Data Gaps (re-checked September 9, 2026)
| Area | Status | Detail |
|---|---|---|
| TEG 2026 exhibitor names | **Largely resolved (~66 named)** | The official TEG sponsors brochure (`teg-sponsors-brochure.pdf`) "Our Exhibitors (Year 2026)" page names ~66 TEG 2026 exhibitors — the first machine-legible resolution of the previously ~74 unnamed homepage logo slots. As of August 31, 2026 all ~66 have individual profiles under `exhibitors/companies/` (50 newly created, 18 pre-existing TEG 2024 profiles annotated). Booth numbers confirmed for a few: Eternal Web (A48–A55), TechnoBrains (A71–72), Perigeon (A144). Two brochure logos remain unidentified entities (Splededge, Ittive); AP and AIWI were resolved via TEG-team-provided URLs (Apicem Partners; Aiwi Software Solutions). **Re-checked Sept 9, 2026 via headless-browser render of both the exhibitor-booking page and the ticketing portal: neither exposes a live/current exhibitor count — the ~66-named brochure figure remains the best available number**, still short of 250+. Full list: `exhibitors/exhibitors_directory.md` and `exhibitors/companies/companies_index.md`. |
| TEG 2026 speaker lineup | **Still unresolved** | No individually named TEG-2026-specific keynote speakers found beyond the same three recycled promo-testimonial names (Ankur Warikoo, Savjibhai Dholakia, Sonu Sharma). Broad web/press/LinkedIn search turned up nothing new. See `speakers/speakers_and_agenda.md`. |
| TEG 2026 visitor ticket pricing | **Still unresolved (re-confirmed, not newly resolved)** | A third-party page (technobrains.io) states the ticket structure has two named tiers — **"Regular Visitor"** and **"Golden Ticket"** — but exact rupee pricing for either tier is still not published anywhere found. **Re-checked Sept 9, 2026 with a full headless-browser render of events.techexpogujarat.com (not a static fetch): still no price tiers rendered, and the tier names themselves don't independently reappear on the official portal** — they trace only to technobrains.io. Saying this plainly per KB convention: unresolved, and this pass did not move it forward. See `registration/registration_and_passes.md`. |
| TEG 2026 detailed session agenda | **Still unresolved** | Not published on the official site or any third-party page found. |
| Accommodation/Travel Partner names | **Still unresolved** | Sponsorship categories ("Official Accommodation Partner," "Official Traveling Partner") remain unfilled — no confirmed company names found. See `sponsors_partners/sponsors_and_partners.md`. |
| TEG 2024 attendee-count conflict (3,000+ vs. 8,000+) | **Documented, not resolved** | 5 of 8 independently-checked exhibitor/press pages use "3,000+" (vs. the KB's sourced 8,000+ actual / 15,000+ target); evidence table + working theory (stale pre-event copy) added Sept 9, 2026 — the KB's primary figures are unchanged. See `past_editions/past_editions_history.md`'s Data Quality Note. |
| Nilay Khandhar's company affiliation | **New conflict, unresolved** | The live ticketing-portal team list names him "CEO, Xpro.Ai Event Tech Private Limited"; this KB (and his own profile) has "CEO, Green Apex Solutions." Found Sept 9, 2026, not resolved this pass. See `organizers_team/organizers_and_team.md`. |
| AIMED TECH EXPO GUJARAT LLP legal/financial detail | **Resolved this pass** | MCA-derived filing history (partners, capital, charges, litigation) added Sept 9, 2026 — see `organizers_team/organizers_and_team.md`. One aggregator (falconebiz.com) returned an unreconciled alternate name ("TECHEXPO VENTURES LLP") for the same LLPIN — flagged, not resolved. |
| Social-media follower counts | **Resolved this pass** | LinkedIn (4,501) and Instagram (7,162) followers confirmed via direct fetch; Facebook (489 likes) confirmed only via a search-result snippet (direct fetch blocked). See `digital_presence/digital_channels.md`'s new "Digital momentum" section. |

### New findings this pass (not previously in the KB)
- **TEG mobile app identified:** "Tech Expo Gujarat" app (`com.greenapex.techexpogujarat`), publisher confirmed as **Green Apex Technolabs LLP** via direct Indus Appstore fetch (Play Store/App Store pages themselves unfetchable — see `digital_presence/digital_channels.md` for the verification note and an unreconciled entity-name nuance vs. Nilay Khandhar's "Green Apex Solutions").
- **Independent press corroboration** of the TEG Ignite 2026 launch event (News Monks) — independently re-fetched and confirmed August 27, 2026. Surfaced an **unreconciled date discrepancy**: News Monks says the launch was "April 4, 2026," while techexpogujarat.com's own /teg-ignite-2026/ page says 3 April 2026. See `related_events/related_events.md`.
- **Perigeon** (Booth A144) independently re-verified by direct re-fetch of perigeon.com — confirmed exhibiting at TEG 2026, 27–29 Nov 2026, GUCEC. See `exhibitors/exhibitors_directory.md`.
- Confirmed via re-crawl: the 12 core organizers and 12 co-organizers, dates (27–29 Nov 2026), venue (GUCEC), and theme are all unchanged from the last update — no organizing-team or date/venue changes found.
- **Verification pass note (August 27, 2026):** all four external claims above (Perigeon, News Monks, EFY Expo, TECH VAPI) were independently re-fetched from their source URLs rather than trusted from the prior pass's summary; all four checked out. The raw 74-filename logo list previously added to `exhibitors_directory.md` was trimmed to a one-line summary (no informational content was lost — the filenames carried no company-identifying data).

### September 9, 2026 pass — new findings
- **Live exhibitor/sponsor/ticketing portals re-checked with a headless browser** (JS fully rendered, not a static fetch — these pages are `robots`-disallowed and dynamic): exhibitor category list (Software/IoT/Marketing/ERP/AI/SaaS/Other) confirmed unchanged; no live exhibitor count found anywhere; no visitor ticket pricing found anywhere; `/become-a-sponsor/`'s live tier list cross-checked against `sponsors_partners/sponsors_and_partners.md` — already consistent, no new tiers. See `exhibitors/exhibitors_directory.md` and `registration/registration_and_passes.md`.
- **Digital momentum added:** LinkedIn 4,501 followers, Instagram 7,162 followers (both direct fetch), Facebook 489 likes (search-snippet only, direct fetch blocked). See `digital_presence/digital_channels.md`.
- **Attendee-count conflict (3,000+ vs. 8,000+/15,000+) documented with an evidence table**, not resolved: 5 of 8 independent sources checked use "3,000+"; working theory is stale pre-event TEG-2024 copy, not a genuine dispute of the post-event actual. KB's primary 8,000+/15,000+ figures unchanged. See `past_editions/past_editions_history.md`.
- **AIMED = Ahmedabad IT Management Executive Delegation, decoded in full**: closed peer community, membership by reference and approval, TEG is one of several AIMED initiatives. Replaces the prior one-line description. See `organizers_team/organizers_and_team.md`.
- **AIMED TECH EXPO GUJARAT LLP legal/financial subsection added**: 4 designated partners unchanged since incorporation, no registered charges, no litigation found, latest filing references 31 March 2025. One aggregator (falconebiz.com) returned an unreconciled alternate entity name ("TECHEXPO VENTURES LLP") for the same LLPIN — flagged, not resolved. See `organizers_team/organizers_and_team.md`.
- **New unreconciled conflict found:** the live ticketing-portal team list names Nilay Khandhar "CEO, Xpro.Ai Event Tech Private Limited," not "CEO, Green Apex Solutions" as elsewhere in this KB. See `organizers_team/organizers_and_team.md`.
- **New file: `competitive_landscape/adjacent_events.md`** — separated from `related_events/related_events.md` (TEG's own satellite events). Documents FITAG National Tech Expo 2026 (new to this KB — 9–10 Jan 2026, Gandhinagar, Federation of IT Associations of Gujarat, 150+ exhibitors/10,000+ channel partners, no AIMED/TEG affiliation) plus EFY Expo Gujarat 2026 and TECH VAPI 2026 (moved from `digital_presence/digital_channels.md`, where they'd been noted more briefly).
- **"AIMED member?" column added** to the exhibitor tables in `sector_wise_participation.md` (19 sector tables, 143 rows) and `exhibitors/exhibitors_directory.md` (2 tables, 151 rows). Filled "Yes" only where a company's own promo material explicitly states AIMED membership (Codevision Technologies, Green Apex, TechnoBrains) — everyone else is "Unknown," not guessed.

---
*Last updated: September 9, 2026 (research pass: live headless-browser re-check of exhibitor/sponsor/ticketing portals; social digital-momentum section added; TEG-2024 attendee-count conflict documented with an evidence table; AIMED decoded in full + legal/financial filing subsection added; new Nilay Khandhar affiliation conflict flagged; new `competitive_landscape/adjacent_events.md` file, incl. newly-found FITAG National Tech Expo; "AIMED member?" column added to `sector_wise_participation.md` and `exhibitors/exhibitors_directory.md`. Sept 1 pass: added `event_goals_and_problem.md` — TEG's goals, the problem it solves, and a per-persona pain-point library; also site re-crawled — early-bird ticket offer reduced 60% → 50% and the "2,600+ sold" figure removed, updated in `registration/registration_and_passes.md`, `event_overview/event_info.md`, `pricing/pricing_and_packages.md`. The /industries/ page still lists the same 18 industries as icons only — no per-sector integration content added. August 31 pass: added 48 new TEG 2026 brochure exhibitor company profiles + annotated 18 existing profiles; earlier content re-verified August 27, 2026)*
*Sources: teg-sponsors-brochure.pdf ("Our Exhibitors — Year 2026" page); techexpogujarat.com full crawl (homepage, about-us, our-team, contactus, become-an-exhibitor, become-a-sponsor, tech-expo-2024, retreat-2025, teg-ignite-2026, product-owners) + events.techexpogujarat.com (incl. live headless-browser render, Sept 9, 2026) + third-party exhibitor/press pages (eternalsoftsolutions.com, technobrains.io, perigeon.com, thecodevision.com, theonetechnologies.com, fintegrationfs.com, digitalterminal.in) + press (newsmonks.com, ncnonline.net, dqchannels.com) + app stores (Google Play, Apple App Store) + social (linkedin.com/company/techexpogujarat, instagram.com/techexpogujarat — direct fetch; facebook.com/TechExpoGujarat — search snippet only) + MCA-derived legal aggregators (thecompanycheck.com, falconebiz.com) + aimedit.org (indirect, direct fetch blocked) + broad web search for exhibitor/speaker/sponsor/accommodation/competitor announcements*
