---
description: Run the full verification gate on the current state and report honestly
---
Run every applicable check and paste REAL output: typecheck · lint · unit+integration tests · build · migrations up/down on scratch DB (if changed) · UI render at 360/768/1280 (if UI changed) · `npm audit`/`pip-audit` high+critical.
Verdict per check: green/red. Any red = list the failing loop to reopen. No "should pass". No summary without evidence.
