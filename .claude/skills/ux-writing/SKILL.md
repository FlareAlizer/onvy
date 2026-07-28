---
name: ux-writing
description: Anti-slop writing for UI copy, docs, error messages, marketing text, and commit/PR prose. Use whenever producing user-facing text, microcopy, README/landing copy, or when the user asks to write/edit any prose — removes predictable AI writing patterns.
---

# UX Writing / Anti-Slop

Adapted from stop-slop (Hardik Pandya) for product development.

## Core rules

1. Cut filler: throat-clearing openers ("It's worth noting", "Let's dive in"), emphasis crutches ("truly", "seamlessly", "robust", "comprehensive"), adverb spam.
2. Break formulas: no "not X, it's Y" contrasts; no rhetorical setups ("So what does this mean?"); no dramatic one-line paragraph endings; no rule-of-three reflex.
3. Active voice, human subjects. Not "the decision was made" — who decided. No inanimate objects doing human verbs ("the feature empowers").
4. Be specific: name the thing, the number, the button. "Faster" → "loads in 0.8s". No lazy extremes (always/never/every) doing vague work.
5. Vary rhythm; two items beat three; em-dash budget: near zero.
6. Trust the reader: state facts, skip hand-holding and self-justification. Cut anything that sounds like a pull-quote.

## UI microcopy

- Buttons: verb-first, outcome-named ("Create invoice", not "Submit"/"OK"). Destructive buttons name the object ("Delete 3 files").
- Errors: what happened + how to fix, in the user's language. Never "An error occurred", never blame ("Invalid input" → "Email needs an @").
- Empty states: one line of what belongs here + the action to create it. Not a poem.
- Confirmations state consequence: "This deletes the project and its 14 deployments. This can't be undone."
- Placeholders show format examples, never replace labels. Sentence case everywhere; no Title Case Buttons.
- Loading: name the work if >2s ("Importing 1,200 rows…"), else spinner silence.

## Engineering prose (commits, PRs, docs)

Commits: imperative, what+why, ≤72 char subject. PR description: problem → approach → how verified (real commands/output) → risks. Docs: every code block runnable; delete "simply" and "just".

## Check before delivering any prose

Adverbs? Passive? "here's what" throat-clear? Three same-length sentences in a row? Marketing filler in engineering text? Fix, then ship.
