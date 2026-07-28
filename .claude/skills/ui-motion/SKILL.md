---
name: ui-motion
description: Motion and animation craft for web UI — timing, easing, springs, gestures, enter/exit, reduced motion, performance. Use whenever adding or reviewing animations, transitions, gestures, drag/swipe/sheet interactions, or when the user mentions animation, анимация, motion, transitions, "оживить".
---

# UI Motion

Distilled from Emil Kowalski's design-engineering philosophy + Apple motion principles.

## When to animate (and when not)

Animate to: explain spatial change (where did it go), soften state changes (enter/exit), give feedback (press, success), guide attention ONCE. Do NOT animate: high-frequency ops a user repeats all day (Operate surfaces — speed beats charm), things that block input, anything purely decorative that loops forever.

## Values that feel right

- UI transitions: **150–300ms**. Micro-feedback (press, toggle): 100–150ms. Larger spatial moves (sheets, page): 300–450ms.
- Easing: **ease-out for entrances** (fast start, settle), ease-in for exits, ease-in-out for moves within view. Never linear for UI (only for marquee/progress).
- Springs for gesture-driven UI (drag, sheets, swipe): stiffness ~200–300, damping ~25–35; must be **interruptible** — a new gesture retargets mid-flight, never queues.
- Enter/exit pairs: exit slightly faster than enter. Scale entrances from 0.95–0.97, not 0. Combine opacity + small translate (4–12px) for "pop in".
- Stagger lists 20–40ms per item, cap total ≤400ms.

## Physical / gesture rules (Apple-style)

Content tracks the finger 1:1; release momentum carries with friction; rubber-band at bounds (resistance ~0.5). Sheets: drag-to-dismiss with velocity threshold, not distance alone. Everything interruptible.

## Performance & a11y

- Animate **transform and opacity only**; never top/left/width/height/box-shadow on the fly (use pseudo-element opacity for shadow fades).
- `will-change` sparingly and removed after. No layout thrash (batch reads/writes).
- `prefers-reduced-motion`: replace movement with opacity fades or nothing; gestures still work, flourishes die.

## Tools

CSS transitions for simple state; Web Animations API or Motion (framer-motion) for orchestration/springs; FLIP for layout moves. Tailwind: define named keyframes in config, don't inline chaos.

## Review bar

Every animation answers "what does this explain or confirm?" in one sentence, or it's cut. Default to flagging; motion approval is earned.
