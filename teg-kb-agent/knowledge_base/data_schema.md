# Internal Data Fields Schema — TEG 2026

> **Purpose:** Maintain consistent data across all TEG records
> **Document type:** Proposed internal schema — a structural template, not a factual claim about the event
> **Last updated:** August 2026

---

## 1. Event Data

| Field | Type | Required | Description |
|---|---|---|---|
| Name | String | Yes | "Tech Expo Gujarat 2026" |
| Year | Integer | Yes | 2026 |
| Status | String | Yes | Announced / In Progress / Completed |
| Date | Date | Yes | 27–29 November 2026 |
| Time | String | Yes | 9:30 AM onwards |
| Venue | String | Yes | GUCEC, Ahmedabad |
| City | String | Yes | Ahmedabad |

---

## 2. Audience Data

| Field | Type | Required | Description |
|---|---|---|---|
| Visitor target | Integer | Yes | 15,000+ |
| Decision-maker target | Integer | Yes | 15,000+ |
| Industries | Array | Yes | List of 18 industries (see `faq/faq_event.md`) |

---

## 3. Exhibitor Data

| Field | Type | Required | Description |
|---|---|---|---|
| Company name | String | Yes | Full legal name |
| Category | String | Yes | Technology type |
| Product | String | No | Primary product/service |
| Booth number | String | No | Stall assignment |
| Contact name | String | No | Primary contact |
| Contact email | String | No | Email address |
| Website | String | No | Company URL |
| Confirmation status | String | Yes | Confirmed / Pending / Waitlisted |

---

## 4. Speaker Data

| Field | Type | Required | Description |
|---|---|---|---|
| Name | String | Yes | Full name |
| Designation | String | Yes | Role and company |
| Topic | String | No | Session title |
| Confirmation status | String | Yes | Confirmed / Pending / Declined |
| Session date | Date | No | Scheduled date |
| Session time | String | No | Scheduled time |
| Session track | String | No | Track/category |

---

## 5. Ticket Data

| Field | Type | Required | Description |
|---|---|---|---|
| Pass type | String | Yes | Regular Visitor / Golden Ticket / other |
| Price | Decimal | No | Rupee amount (not yet published for TEG 2026) |
| Tax | Decimal | No | Applicable tax |
| Inclusions | Array | No | What's included |
| Availability | String | Yes | Available / Sold Out / Limited |

---

## 6. Sponsorship Data

| Field | Type | Required | Description |
|---|---|---|---|
| Tier name | String | Yes | Title / Official AI Partner / etc. (see `sponsors_partners/sponsors_and_partners.md`) |
| Price | Decimal | No | Rupee amount (not yet published for TEG 2026) |
| Tax | Decimal | No | Applicable tax |
| Inventory | Integer | Yes | Number available |
| Benefits | Array | No | What's included |
| Contact person | String | No | Internal contact |

---

## 7. Session Data

| Field | Type | Required | Description |
|---|---|---|---|
| Date | Date | Yes | Session date |
| Time | String | Yes | Start and end time |
| Track | String | Yes | Track/category |
| Topic | String | Yes | Session title |
| Speaker | String | Yes | Speaker name |
| Room | String | No | Venue room/location |

---

## 8. Lead Data

| Field | Type | Required | Description |
|---|---|---|---|
| Name | String | Yes | Full name |
| Company | String | Yes | Company name |
| Role | String | No | Job title |
| Phone | String | Yes | Mobile number |
| Email | String | Yes | Email address |
| Intent | String | Yes | Visitor / Exhibitor / Sponsor / Speaker |
| Status | String | Yes | New / Contacted / Qualified / Lost |
| Callback date | Date | No | Scheduled follow-up |

---

## 9. Compliance Data

| Field | Type | Required | Description |
|---|---|---|---|
| Consent | Boolean | Yes | Received consent to contact |
| Privacy notice | Boolean | Yes | Privacy policy acknowledged |
| Data retention policy | String | Yes | Retention period |

---

*Sources: field definitions are a proposed internal template; the event-identity values populated as examples above (dates, venue, targets) trace to `event_overview/event_info.md` and `INDEX.md`, both sourced from techexpogujarat.com / events.techexpogujarat.com.*
