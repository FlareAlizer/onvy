---
name: grilling
description: Relentless one-question-at-a-time interview to sharpen a spec, plan, decision, or idea before any code is written. Use when the user says "grill me", "прожарь", asks to stress-test thinking, or when a request is ambiguous enough that guessing would risk building the wrong thing.
---

# Grilling

Interview the user relentlessly about every aspect of the plan/spec until shared understanding is reached.

Rules (adapted from Matt Pocock's grilling discipline):
- Walk the decision tree branch by branch, resolving dependencies between decisions one-by-one.
- **One question at a time.** Wait for the answer. Multiple questions at once is bewildering.
- **Attach your recommended answer to every question** ("My recommendation: X, because Y") — the user can just say "да" to accept.
- If a **fact** can be found by exploring the environment (filesystem, code, docs, web) — look it up yourself instead of asking. Only **decisions** go to the user.
- Track resolved decisions; update the spec file (`specs/*.md`) as answers land.
- Done when: an implementer agent could build it without asking a single question. Then read the final spec back in ≤10 bullet points and get explicit confirmation.
- Do not start building until the user confirms.

Question priority order: goal & success metric → users/audience → scope boundaries (what's OUT) → data model & state → integrations/external constraints → security/auth model → UX critical paths → non-functionals (perf, scale, i18n) → deployment target.
