---
description: Full security audit of the current changes or a target area
argument-hint: "[path, feature, or empty = current diff]"
---
Spawn the `security-auditor` subagent on: $ARGUMENTS (default: current git diff + touched modules).
It must follow the `security-hardening` skill checklist and produce the findings table with concrete attack scenarios and a BLOCK/PASS verdict. Then summarize the top 3 risks for me in plain language and ask whether to fix Critical/High items now (each fix = its own loop with a regression test).
