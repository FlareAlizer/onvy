---
name: responsive-adaptive
description: Responsive and adaptive layout engineering — breakpoints, fluid type, container queries, touch ergonomics, mobile-first patterns. Use PROACTIVELY for every UI surface, and whenever the user mentions responsive, adaptive, адаптив, мобильная версия, planshet/tablet, or layouts breaking on some screen.
---

# Responsive & Adaptive

Mobile is a first-class deliverable, not a media-query patch at the end.

## Method

1. Design the 360px layout FIRST (content priority forced), then expand: 360 → 768 → 1024 → 1280 → 1536.
2. Breakpoints follow the CONTENT (where the layout breaks), not devices; standard Tailwind steps are fine anchors.
3. Prefer intrinsic layout over breakpoint forests: `grid-template-columns: repeat(auto-fit, minmax(280px, 1fr))`, flex-wrap, `min()/max()/clamp()`.
4. **Container queries** (`@container`) for components that live in different-width slots — component adapts to its container, not the viewport.
5. Fluid type & space: `clamp(1rem, 0.9rem + 0.5vw, 1.25rem)` for headings/hero; body text stays ≥16px always (also prevents iOS zoom on inputs).

## Mobile ergonomics

- Touch targets ≥44×44px with ≥8px gaps; primary actions in thumb reach (bottom half) on app-like surfaces.
- `100dvh` not `100vh` (mobile URL bar); `env(safe-area-inset-*)` for notches; sticky bottom bars account for keyboards.
- Tables → cards or horizontal-scroll region with sticky first column, chosen per data shape; never let a table silently overflow.
- Nav: top bar + sheet/drawer on mobile; hover-only interactions get tap equivalents; no hover-reveals hiding critical actions.
- Long words/URLs: `overflow-wrap: break-word`; truncation with title/tooltip only when full value is reachable elsewhere.

## Media & performance on mobile

`srcset/sizes` or framework Image with correct sizes; explicit width/height (CLS=0); lazy-load below the fold; test on throttled 4G, not just localhost.

## Verification (part of the loop's Definition of Done)

Render at **360, 768, 1280** minimum + one awkward middle (~900px). Check: nothing overflows horizontally, tap targets pass, text ≥16px, no CLS jumps, keyboard doesn't cover focused inputs, landscape phone isn't broken.
