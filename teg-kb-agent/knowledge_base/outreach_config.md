# Outreach Configuration — TEG 2026

> **Purpose:** Configuration rules for the 3-agent outreach pipeline
> **Last updated:** August 2026
> **Status:** Draft configuration

---

## Confidence Thresholds

### Company Name Matching
| Match Type | Confidence Threshold | Action |
|---|---|---|
| Exact match (case-insensitive) | 95%+ | Auto-accept |
| Fuzzy match (Levenshtein distance ≤ 2) | 70-94% | Flag for manual review |
| Partial match (contains/substring) | 50-69% | Flag for manual review |
| No match | <50% | Web search required |

### LinkedIn Profile Matching
| Match Criteria | Confidence Threshold | Action |
|---|---|---|
| Name + Company exact match | 90%+ | Auto-accept |
| Name + Company fuzzy match | 70-89% | Flag for manual review |
| Name only match | 50-69% | Flag for manual review |
| No match | <50% | Web search required |

### Sector Classification
| Data Source | Confidence Threshold | Action |
|---|---|---|
| KB sector_wise_participation.md exact match | 95%+ | Auto-accept |
| Company website self-described sector | 80-94% | Auto-accept |
| Third-party directory (Clutch, LinkedIn) | 60-79% | Flag for manual review |
| Web search inference | 40-59% | Flag for manual review |
| No data available | <40% | Ask user for clarification |

---

## Field Classification

### Hard Requirements (Never Enrich)
These fields must come directly from the form submission:
- Email
- Phone
- Consent to contact

### Enrichable Fields (Can be researched)
These fields can be filled via KB lookup or web search:
- Designation/Role
- LinkedIn profile URL
- Company sector
- Company size
- Company website (if not provided)
- Prior TEG involvement

---

## Output Format Rules

### Email Format
**Trigger:** Intent = "exhibitor" OR "visitor"
**Structure:**
```
Subject: [Personalized] TEG 2026: [Value proposition for their sector]

Dear [Name],

[Opening - acknowledge their company and sector]

[Value proposition from exhibitor_benefits_analysis.md matching their persona]

[Social proof - 3-5 peer companies from their sector already participating]

[Specific ask based on their participation type]

[Call to action - next steps]

Best regards,
TEG Team
```

### Landing Page Format
**Trigger:** Intent = "sponsor"
**Structure:**
```
[Hero section with personalized headline]

[Why TEG 2026 for [Company Name] - sponsor persona benefits]

[Peer sponsors in their category]

[Sponsorship tiers available]

[Contact form/CTA]
```

### Welcome Back Format
**Trigger:** Existing relationship (organizer/exhibitor from KB)
**Structure:**
```
Subject: Welcome back to TEG 2026, [Name]

Dear [Name],

[Acknowledge their past involvement - specific details from KB]

[What's new in TEG 2026 relevant to them]

[Ask for their continued participation]

[Personal sign-off from relevant organizer if applicable]
```

### JSON Format
**Trigger:** Integration with CRM/system
**Structure:**
```json
{
  "lead_id": "[ID]",
  "enriched_profile": {
    "name": "[Name]",
    "company": "[Company]",
    "role": "[Role]",
    "sector": "[Sector]",
    "linkedin": "[URL]",
    "confidence_scores": {
      "sector": 0.95,
      "role": 0.80,
      "linkedin": 0.90
    }
  },
  "personalization": {
    "persona": "IT Services / AI Startup / Sponsor",
    "peer_companies": ["Company A", "Company B", "Company C"],
    "value_propositions": ["Prop 1", "Prop 2"]
  },
  "recommended_outreach": {
    "format": "email",
    "subject": "[Subject line]",
    "body": "[Full message]"
  }
}
```

---

## Persona Mapping Rules

### IT/Tech Service Company
**Trigger:** Sector in [Software Development, Cloud & Infrastructure, Enterprise Software, Data & Analytics]
**Persona:** IT Services from exhibitor_benefits_analysis.md
**Key Value Props:**
- Access to 15,000+ decision-makers across industries
- Pre-scheduled B2B meetings
- Multi-industry exposure
- Live product demonstration opportunities

### AI/Deep-Tech Startup
**Trigger:** Sector in [AI & Machine Learning] AND company size < 50 employees
**Persona:** AI Startup from exhibitor_benefits_analysis.md
**Key Value Props:**
- Catalyst Zone (affordable startup stalls)
- Experience Zone for AI demos
- VC network access (₹1.5 crore funding track record)
- Networking with industry leaders

### Non-Tech Sponsor
**Trigger:** Intent = "sponsor" AND sector in [Manufacturing, Automobile, Real Estate, etc.]
**Persona:** Non-Tech Sponsor from exhibitor_benefits_analysis.md
**Key Value Props:**
- Brand exclusivity in category
- C-suite networking
- Omnichannel visibility
- Association with AI revolution narrative

### Visitor
**Trigger:** Intent = "visitor"
**Persona:** Visitor conversion from inquiry_page_content.md
**Key Value Props:**
- Discover AI/tech solutions across sectors
- Meet providers in one place
- Build business connections

---

## Guardrails

### Fact Verification
- **Never mix "Confirmed" and "Awaiting Confirmation" claims**
- All statistics must cite source files (event_info.md, exhibitors_directory.md)
- Peer company lists must come from sector_wise_participation.md
- No fabricated testimonials or social proof

### Personalization Limits
- Do not invent details about the company or person
- If confidence < 70% on any field, use generic language or ask for clarification
- Never assume budget, timeline, or decision authority

### Outreach Frequency
- Maximum 1 outreach per week per lead
- Stop outreach if lead status = "Lost" or "Declined"
- Respect "Do not contact" flags

---

## Manual Review Triggers

The following conditions require human review before outreach:
- Company name fuzzy match (70-94% confidence)
- LinkedIn profile fuzzy match (70-89% confidence)
- Sector classification from third-party sources (60-79% confidence)
- Existing relationship detected (organizer/exhibitor) - for tone calibration
- Sponsorship inquiry (high-value, requires personalized handling)

---

*Source: Configuration derived from data_schema.md, inquiry_page_content.md, exhibitor_benefits_analysis.md, sector_wise_participation.md*
