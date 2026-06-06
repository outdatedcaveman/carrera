# Application-form auto-fill — roadmap

## The problem

Today Carrera produces the *artifacts* for an application — tailored résumé
PDF and cover letter — and tracks status in the Pipeline tab. But the actual
application is still 20–60 minutes of manual typing per role:

- Workday's 30-step wizard
- Greenhouse / Lever / Ashby / Gupy / SmartRecruiters forms
- LinkedIn Easy Apply (sometimes one click, often a full form)
- Workday-clone ATSes embedded on company career sites

Most of the friction is in **the boring parts**: name, email, phone,
LinkedIn URL, work-authorization checkboxes, salary expectation in the
right currency, notice period, education dropdowns, race / gender /
disability "voluntary self-identification" pages. Then a handful of
free-text questions ("why this role?", "tell me about a time…") that
should be drafted from the cover letter + CV the user already paid the
LLM to generate.

A user applying to ten roles a week spends 5–10 hours/week on boilerplate
data entry. That's the headline target.

## Why this is harder than it looks

There's no API. Every ATS exposes a different DOM. Workday alone has at
least three template variants in the wild. Career sites embed customized
versions. Cookie consent walls, CAPTCHAs, MFA, and "save your progress"
dialogs interrupt every form. A few platforms (Workday especially) put the
form behind a session-bound token so even URL-replay across sessions
breaks.

So the architecture has to assume:

1. **DOM is the API**. We need to drive a real browser, not call REST.
2. **Human-in-the-loop is non-negotiable** for anything legally
   meaningful (work authorization, sponsorship, criminal record, background
   check consent). The user reviews and clicks Submit.
3. **The user wants to see what's being typed.** A headless background
   process that "just submits" feels creepy and is also fragile — when
   it breaks, the user has no idea where it stopped.
4. **Free-text questions need the job context**. "Why this role?" gets a
   different answer for every job, and the answer should reuse the same
   evidence the cover letter already cited.

## Architecture — three layers

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3: Browser autofill (Playwright)                         │
│  Drives the real ATS form. Sees the DOM, matches fields to      │
│  Layer 1 answers, types them in. User watches and submits.      │
├─────────────────────────────────────────────────────────────────┤
│  Layer 2: Per-job answer generator                              │
│  For each application, generates job-specific answers to        │
│  free-text questions (why this role? salary? availability?)     │
│  using the tailored CV + cover letter + Layer 1 facts.          │
├─────────────────────────────────────────────────────────────────┤
│  Layer 1: Quick Answers store                                   │
│  Profile-level static answers — work auth, salary range,        │
│  diversity self-ID, notice period, links. The "1Password for    │
│  job applications". Read by Layer 2 and Layer 3, edited in      │
│  Settings, also displayed inline next to a job for copy/paste.  │
└─────────────────────────────────────────────────────────────────┘
```

Build order: **L1 first, L2 next, L3 last**. L1 is the foundation —
useful even alone (copy buttons next to a Workday form save real time)
and doesn't require a headless browser, so it ships fast and de-risks
the harder layers.

## Layer 1 — Quick Answers (this PR)

A flat key-value store of answers a user gives the same way every time.
Categories:

- **Identity**: full name, email, phone, current city, LinkedIn, website,
  preferred name, pronouns. Auto-derived from the default CV where
  possible — the user only edits the gaps.
- **Work authorization**: country-of-residence, citizenship, visa status,
  authorized to work in [EU / US / UK / BR] (Y/N each), sponsorship
  required (Y/N).
- **Compensation**: target salary minimum (per currency), preferred currency,
  open to equity, open to commission.
- **Logistics**: notice period (weeks), earliest start date, willing to
  relocate, willing to travel %, remote preference, on-site days/week.
- **Background**: highest degree, university, graduation year, total years
  experience, years in current field — derived from CV when possible.
- **Voluntary self-ID** (US-style EEO): gender, race/ethnicity, veteran
  status, disability status. Always optional, defaults to "decline to
  state".
- **Boilerplate prose**: a 2–3 sentence elevator pitch, a "tell me about
  yourself" intro, "why are you looking?" paragraph, "biggest strength /
  weakness" canned answers.

Surface in two places:
- **Settings → Quick Answers** for editing
- **Job detail view → Quick Answers panel** with one-click copy buttons.
  Also accessible from a hovering bookmarklet/extension later.

Storage: JSON column on a singleton row (the user has one set of answers,
not many — keep it simple). A schema-versioned blob is easier to evolve
than a wide table of nullable columns.

## Layer 2 — Per-job answer generator

When the user runs Tailor Resume on a job, also generate (cheaply, in
the same LLM round-trip) answers to the recurring open-ended questions:

- "Why are you interested in this role?"
- "Why do you want to work at {company}?"
- "What's your relevant experience for this position?"
- "What salary are you targeting?" (uses Layer 1 + adjusts for currency
  if the JD is in a different country)
- "When can you start?" (computes from Layer 1 notice period + today)

These are stored on the `TailoredApplication` row alongside the cover
letter, so the Apply view can show them inline next to copy buttons.

Cost: marginal — same context the cover-letter prompt already pays for.

## Layer 3 — Browser autofill

The hard one. Pluggable per-ATS adapters with a generic LLM fallback.

**Per-ATS adapters** (highest ROI): Workday, Greenhouse, Lever, Ashby,
SmartRecruiters, Gupy. Each is a small Python module that knows the DOM
selectors for that ATS and maps its fields to Quick Answers keys.

**Generic LLM filler**: for unknown ATSes, screenshot the page, send the
DOM + answers to the LLM, get back a list of `{selector, value, action}`
ops, run them. Slower and more error-prone but covers the long tail.

Driver: **Playwright**, launched in **headed** mode so the user watches
it work. Carrera opens the application URL, navigates to the form,
fills what it can, then surfaces a panel that lists every field it
filled and every field it skipped, with the source value highlighted.
User reviews, edits anything wrong, clicks Submit themselves.

Two integration shapes, in increasing order of polish:
1. **"Open in Carrera browser"** button on a job — launches Playwright
   in a window. Easy to ship, requires Playwright + Chromium bundled
   into the exe (heavyweight: ~250MB).
2. **Browser extension** (later) — Chrome/Edge extension reads the DOM
   of the user's normal browsing tab, calls the local Carrera API, and
   types into the page. Lighter weight for the user, more code for us.

Likely we ship #1 first as a "Pro mode" toggle.

## What this PR implements

Just Layer 1 — the Quick Answers store, settings UI, and a job-detail
panel with copy-to-clipboard buttons. Layer 2 and Layer 3 are tracked
in this doc and follow on.

## Open questions / tradeoffs

- **Single store vs. per-job overrides?** First pass: single. If the user
  has multi-currency salary targets that vary by region, they edit before
  copying. Per-job overrides are a Phase 1.5 if it becomes a pain.
- **Diversity self-ID — pre-fill or always blank?** Always optional and
  always reviewable. Default to "decline to state" rather than a guess
  derived from CV.
- **Where do free-text answers live — Quick Answers (static) or
  TailoredApplication (per-job)?** Both. Quick Answers has the canned
  fallback, TailoredApplication has the job-specific generated version.
  UI shows the per-job version when available, the canned one otherwise.
- **Browser extension vs Playwright?** Playwright wins on shipping speed
  (no extension review process, no per-browser variants) and on the
  "watch it work" UX. Extension is better long-term once the patterns
  are stable.
