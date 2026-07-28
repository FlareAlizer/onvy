---
name: design-taste
description: Anti-slop visual design system for web UI — design reads, dials, tokens, layout, typography, color, and the banned-defaults list. Use PROACTIVELY for ANY new UI surface (landing, dashboard, app screen, portfolio, form), any redesign, and whenever the user mentions design, дизайн, красиво, UI, стиль, or references other products' look.
---

# Design Taste

Distilled from tasteskill + impeccable + this profile's standards. Every rule is contextual — read the brief first.

## 1. The Design Read (before any pixels)

Infer and STATE in one line: "Reading this as: <page kind> for <audience>, with a <vibe> language, leaning <aesthetic family / system>."
Signals: page kind (landing/portfolio/app/editorial), vibe words the user used, references linked, audience (B2B buyer ≠ design-conscious consumer ≠ recruiter), existing brand assets, quiet constraints (regulated, accessibility-first, kids) — constraints OVERRIDE aesthetics.
If the read genuinely diverges two ways, ask exactly ONE question. Otherwise declare and proceed.

## 2. Three dials (set per surface, gate everything)

- `DESIGN_VARIANCE` 1–10 (perfect grid ↔ artsy chaos) — B2B ops UI ≈ 2–3, landing ≈ 5–7, creative portfolio ≈ 8+
- `MOTION_INTENSITY` 1–10 — Operate surfaces ≤3, Persuade 4–6, Experience up to 8
- `VISUAL_DENSITY` 1–10 (gallery ↔ cockpit) — marketing 3–4, dashboards 6–8

## 3. Modes

**Persuade** (landing/pricing): design IS the product; earn attention, one primary CTA per viewport. **Operate** (app/dashboard): scanability, consistency, native expectations beat expression; brand lives in details. **Read** (docs/blog): comprehension structure, then a reading experience worth staying in. **Experience** (portfolio): the work leads, interface recedes. A tool's landing is still Persuade.

## 4. Banned defaults (the slop list)

Unless the brief explicitly asks: AI-purple/indigo gradient washes · centered hero over dark mesh/starfield · three identical feature cards with emoji icons · glassmorphism on everything · infinite floating/pulsing micro-animations · Inter + slate-900 as a reflex · fake testimonials/logos · stock 3D blobs. Reach past defaults *deliberately* based on the read.

## 5. Tokens first (any new surface)

Define once, use everywhere:
- **Type scale**: pick a real scale (e.g. 1.25 ratio), 2 families max (display + text/mono), body ≥16px, line-height ≥1.45 body / ≤1.2 display, measure 45–75ch.
- **Spacing**: 4/8-based scale; whitespace proportional to grouping (proximity = relationship).
- **Color roles**: bg / surface / border / text / muted / accent / danger / success — not hex-soup. One accent doing real work. AA contrast enforced. Dark mode = designed palette, not inverted.
- **Radius & shadow**: one small scale each; shadows imply elevation consistently.

## 6. Layout & hierarchy

One primary action per view. Scan path obvious in 3s. Asymmetry and scale contrast create interest at higher variance dials; a strict grid creates trust at lower ones. Align optically, not just numerically. Edges breathe on mobile (≥16–24px gutters).

## 7. Ship floor (every surface)

States designed: hover/active/focus/disabled/loading/empty/error/long-content. Focus visible. Touch targets ≥44px. Images sized (no CLS). Reduced-motion respected. Verify 360/768/1280.

## 8. Heavier lifting

For deep passes use the installed third-party packs when present: `impeccable` (critique/audit/polish/animate/typeset commands), `design-taste-frontend` (tasteskill, landings/portfolios), Emil Kowalski's `apple-design`/`emil-design-eng`. This skill sets the floor; those raise the ceiling.
