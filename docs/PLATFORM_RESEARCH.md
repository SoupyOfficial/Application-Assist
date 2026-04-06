# Platform Expansion Research

**Last updated:** 2025-04-05
**Purpose:** Document unsupported ATS platforms, prioritize expansion, and track implementation complexity.

---

## Current Coverage

| Platform | Adapter | Detection | Notes |
| --- | --- | --- | --- |
| Greenhouse | `greenhouse.py` | URL + DOM | Single-page, iframe embed (`#grnhse_iframe`) |
| Lever | `lever.py` | URL + DOM | Single-page, clean semantic HTML |
| Ashby | `ashby.py` | URL + DOM | React SPA, `data-ashby-*` attributes |
| Workday | `workday.py` | URL + DOM | Multi-step wizard, `data-automation-id`, custom override |
| Generic | `generic.py` | Fallback | DOM scan with shadow DOM fallback |

---

## Tier 1 — High Market Share (Priority: High)

### Oracle Taleo

- **Market share:** Largest enterprise ATS globally. Dominates Fortune 500 hiring.
- **URL patterns:** `*.taleo.net`, `*.oracle.com/careers`, `career*.taleo.net/careersection/*`
- **Form characteristics:**
  - Multi-page wizard (similar to Workday)
  - Heavy use of iframes and Java-era HTML patterns
  - Uses `<table>` layouts extensively — fields are NOT in semantic `<label>/<input>` pairs
  - Session management is strict — automation can trigger session timeouts
  - Login wall almost always required (Oracle account or guest flow)
- **Detection signals:** `taleo.net` in URL, `careersection` path segment, `<meta name="generator" content="Taleo">`
- **Implementation complexity:** HIGH — table-based layout requires custom field discovery; session management needs careful handling
- **Recommendation:** Add as Tier 1 adapter. Override `fill_form()` like Workday for multi-step. Custom `detect_fields()` to handle table layouts.

### iCIMS

- **Market share:** Very large. Common in mid-to-large enterprises, healthcare, government.
- **URL patterns:** `*.icims.com`, `jobs-*.icims.com`, `careers-*.icims.com`
- **Form characteristics:**
  - Loads application in an iframe
  - Mix of standard HTML forms and custom widgets
  - Multi-page flow (personal info → experience → questions → review)
  - Uses `id` attributes with patterns like `input-field-*`
- **Detection signals:** `icims.com` in URL, iframe src containing `icims`, `<div class="iCIMS_*">`
- **Implementation complexity:** MEDIUM — iframe handling already exists; main work is CSS selectors for field detection
- **Recommendation:** Add detector + adapter. Iframe resolved by existing `get_form_frame()`. Focus on mapping iCIMS-specific field `id` patterns.

### SAP SuccessFactors

- **Market share:** Large. Common in global enterprises, especially non-US companies.
- **URL patterns:** `*.successfactors.com`, `*.successfactors.eu`, `performancemanager*.successfactors.com`
- **Form characteristics:**
  - Multi-page wizard
  - Heavy JavaScript, React-like SPA
  - Uses custom UI5 components (SAP's own UI framework)
  - Shadow DOM possible for SAP UI5 widgets
  - Login typically required
- **Detection signals:** `successfactors` in URL, `sap-ui-*` CSS classes, `data-sap-*` attributes
- **Implementation complexity:** HIGH — SAP UI5 components may resist standard CSS selectors; shadow DOM piercing needed
- **Recommendation:** Defer until after iCIMS. UI5 component handling requires investigation.

### SmartRecruiters

- **Market share:** Growing. Popular with mid-size tech companies.
- **URL patterns:** `jobs.smartrecruiters.com/*`, `*.smartrecruiters.com`
- **Form characteristics:**
  - Clean, modern SPA (React-based)
  - Multi-step flow but with good semantic HTML
  - Standard `<input>`, `<select>`, `<textarea>` elements
  - May use `aria-label` instead of visible `<label>` text
- **Detection signals:** `smartrecruiters.com` in URL, `<meta property="og:site_name" content="SmartRecruiters">`
- **Implementation complexity:** LOW-MEDIUM — clean HTML, similar to Lever. Main challenge is aria-label-based field detection.
- **Recommendation:** Prioritize. Relatively easy win. Existing `detect_fields()` patterns should mostly work with minor tweaks.

### BambooHR

- **Market share:** Very large in SMBs (small/mid businesses). Common for startups and small/mid companies.
- **URL patterns:** `*.bamboohr.com/careers/*`, `*.bamboohr.com/jobs/*`
- **Form characteristics:**
  - Iframe-embedded application forms
  - Mix of standard HTML and custom Vue.js components
  - Single-page or two-page flow (info + questions)
  - Clean `<label>/<input>` pairing in most cases
- **Detection signals:** `bamboohr.com` in URL, iframe with BambooHR source, `<div class="BambooHR*">`
- **Implementation complexity:** LOW — iframe already handled by `get_form_frame()`, clean HTML
- **Recommendation:** Prioritize. Easy win. Existing generic adapter may already work with BambooHR forms.

---

## Tier 2 — Common Platforms (Priority: Medium)

### Jobvite

- **URL patterns:** `jobs.jobvite.com/*`, `*.jobvite.com`
- **Form characteristics:** Iframe embed, multi-page, standard HTML forms
- **Detection signals:** `jobvite.com` in URL, iframe detection
- **Implementation complexity:** LOW-MEDIUM — iframe handled, need CSS selectors
- **Recommendation:** Similar to BambooHR. Should be straightforward.

### UKG (Ultimate Kronos Group)

- **URL patterns:** `*.ultipro.com`, `*.ukg.com`, `recruiting.ultipro.com/*`
- **Form characteristics:** Multi-step, enterprise-grade UI, some custom widgets
- **Detection signals:** `ultipro.com` or `ukg.com` in URL
- **Implementation complexity:** MEDIUM — custom widgets may need specific handling
- **Recommendation:** Add when enterprise coverage is needed.

### Breezy HR

- **URL patterns:** `*.breezy.hr/*`
- **Form characteristics:** Clean modern SPA, single-page form, good HTML semantics
- **Detection signals:** `breezy.hr` in URL
- **Implementation complexity:** LOW — likely works with generic adapter already
- **Recommendation:** Test with generic adapter first; add detector if needed.

### JazzHR

- **URL patterns:** `*.applytojob.com/*`, `app.jazz.co/*`
- **Form characteristics:** Simple single-page forms, standard HTML
- **Detection signals:** `applytojob.com` or `jazz.co` in URL
- **Implementation complexity:** LOW — likely works with generic adapter
- **Recommendation:** Test with generic adapter first.

### Rippling

- **URL patterns:** `*.rippling.com/careers/*`
- **Form characteristics:** Modern React SPA
- **Detection signals:** `rippling.com` in URL
- **Implementation complexity:** MEDIUM — React SPA may need SPA-aware waiting
- **Recommendation:** Lower priority. SPA handling in browser helpers may suffice.

---

## Tier 3 — Non-Browser / Non-ATS (Priority: Research)

These platforms fundamentally differ from the current architecture (URL → detect → fill → submit). Supporting them would require new paradigms.

### LinkedIn Easy Apply

- **Volume:** Probably the highest-volume application method for many job seekers.
- **Challenge:** LinkedIn's UI is tightly controlled, anti-automation, locked behind authentication, and uses aggressive bot detection. LinkedIn also has its own browser extension ecosystem.
- **Form characteristics:** Multi-step modal within LinkedIn, pre-populated from LinkedIn profile, typically 1-3 custom questions + resume upload
- **Feasibility:** LOW for automation. LinkedIn actively detects and blocks Playwright/Selenium. Risk of account suspension.
- **Alternative approach:** Browser extension that fills LinkedIn Easy Apply from `answers.json` would be safer than full Playwright automation. Or a helper that prepares answers for the user to manually input.
- **Recommendation:** Do NOT automate LinkedIn directly. Consider a "clipboard helper" mode that copies answers for manual pasting.

### Indeed Apply

- **Volume:** High. Indeed has its own application flow for many job postings.
- **Challenge:** Similar to LinkedIn — authentication required, anti-bot measures, pre-populated from Indeed profile.
- **Feasibility:** LOW-MEDIUM. Less aggressive than LinkedIn but still risky.
- **Recommendation:** Same as LinkedIn — consider helper mode rather than full automation.

### Google Forms / Typeform / Airtable

- **Volume:** Common for startups, small companies, contract roles.
- **Form characteristics:**
  - Google Forms: Standard HTML but within Google's framework. `<div role="listitem">` containers.
  - Typeform: One-question-per-page SPA, custom keyboard navigation, no standard form elements
  - Airtable: Iframe-embedded form, uses React
- **Detection signals:** `docs.google.com/forms`, `*.typeform.com`, `airtable.com/*/form`
- **Implementation complexity:**
  - Google Forms: MEDIUM — DOM structure is unusual but consistent
  - Typeform: HIGH — completely custom UI, one-at-a-time flow
  - Airtable: MEDIUM — iframe + React SPA
- **Recommendation:** Google Forms is the most valuable target. Typeform is low priority due to complexity. Airtable is niche.

### Email-Based Applications

- **Description:** "Send your resume and cover letter to jobs@company.com"
- **Challenge:** Completely outside browser automation. Would need email composition.
- **Feasibility:** Could integrate with `smtplib` or a mail API, but fundamentally different workflow.
- **Recommendation:** Out of scope for v1. Could be a separate module that drafts an email from `profile.json` and a cover letter template.

### PDF Form Applications

- **Description:** Download PDF, fill fields, upload/email back.
- **Challenge:** Requires PDF form filling library (e.g., `PyPDF2`, `fillpdf`, `pdfrw`).
- **Feasibility:** MEDIUM — PDF form filling is well-supported in Python. Detection of PDF downloads and field mapping would be different from HTML forms, but the answer matching engine would still apply.
- **Recommendation:** Interesting future feature. The engine (normalizer, matcher, confidence) is reusable. Only the input (PDF field names) and output (PDF fill instead of Playwright fill) change.

### Company Custom Portals

- **Description:** Bespoke career portals built in-house. No common framework.
- **Challenge:** Every portal is different. No reliable detection or structural expectations.
- **Feasibility:** The generic adapter already handles this as well as possible.
- **Recommendation:** No additional work needed. The generic adapter + shadow DOM fallback covers this.

---

## Implementation Priority Matrix

| Priority | Platform | Complexity | Expected Impact | Effort (days) |
| --- | --- | --- | --- | --- |
| 1 | SmartRecruiters | Low-Medium | Medium-High | 1-2 |
| 2 | BambooHR | Low | Medium | 1 |
| 3 | iCIMS | Medium | High | 2-3 |
| 4 | Jobvite | Low-Medium | Medium | 1-2 |
| 5 | Google Forms | Medium | Medium | 2-3 |
| 6 | Taleo | High | High | 3-5 |
| 7 | JazzHR / Breezy HR | Low | Low-Medium | 0.5 each |
| 8 | SuccessFactors | High | Medium | 3-5 |
| 9 | UKG | Medium | Low-Medium | 2-3 |
| 10 | Rippling | Medium | Low | 1-2 |

**Not prioritized (research only):** LinkedIn Easy Apply, Indeed Apply, Typeform, email-based, PDF forms.

---

## Next Steps

1. **Validate generic adapter** against BambooHR, Breezy HR, and JazzHR — they may already work without custom adapters
2. **Add SmartRecruiters adapter** — clean HTML, high value, low effort
3. **Add iCIMS adapter** — iframe handling exists, need CSS selectors for iCIMS-specific field patterns
4. **Research Google Forms DOM** — determine if worth a custom adapter or if generic can handle it
5. **Defer Taleo and SuccessFactors** until the easier platforms are covered and real-world testing reveals actual user demand

---

*This document is a living research artifact. Update as platforms are investigated, tested, or implemented.*
