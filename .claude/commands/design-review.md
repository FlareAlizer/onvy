---
description: High-bar design/UX review of a surface (hierarchy, tokens, motion, responsive, anti-slop)
argument-hint: "[route, component, or empty = recently changed UI]"
---
Spawn the `design-reviewer` subagent on: $ARGUMENTS (default: UI touched in the current diff).
It follows the `design-taste` + `ui-motion` + `responsive-adaptive` skills: establish the Design Read, check 360/768/1280, run the anti-slop scan, and return SHIP / POLISH NEEDED / REDESIGN with exact-value fixes. If the impeccable pack is installed, additionally run its `critique` playbook for depth. Then propose which findings to fix in this session, ordered by user impact.
