#!/usr/bin/env python3
"""PreToolUse hook for Bash: blocks dangerous commands and secret leaks.
Exit 2 = block (stderr shown to Claude). Exit 0 = allow. Fails open on parse errors."""
import json, re, sys

try:
    data = json.load(sys.stdin)
    cmd = (data.get("tool_input") or {}).get("command", "") or ""
except Exception:
    sys.exit(0)

RULES = [
    (r"rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)[a-zA-Z]*\s+(/|~|\$HOME)(\s|$)", "Blocked: recursive force-delete of / or home."),
    (r"(curl|wget)[^|;&]*\|\s*(sudo\s+)?(ba)?sh", "Blocked: piping remote scripts into shell (curl|sh). Download, inspect, then run."),
    (r"git\s+push\s+[^\n]*(--force|\-f)\b(?![^\n]*--force-with-lease)[^\n]*\b(main|master)\b", "Blocked: force-push to main/master. Use --force-with-lease on a feature branch."),
    (r"git\s+add\s+[^\n]*(\.env(\.\w+)?(\s|$)|id_rsa|\.pem\b)", "Blocked: staging secret files (.env/keys). Add to .gitignore instead."),
    (r"git\s+commit\s+[^\n]*--no-verify", "Blocked: --no-verify skips quality hooks. Fix the underlying issue."),
    (r"\bchmod\s+777\b", "Blocked: chmod 777. Use minimal permissions."),
    (r"DROP\s+(DATABASE|SCHEMA)\b", "Blocked: DROP DATABASE/SCHEMA in raw bash. Do this through a reviewed migration."),
]
for pat, msg in RULES:
    if re.search(pat, cmd, re.IGNORECASE):
        print(msg, file=sys.stderr)
        sys.exit(2)
sys.exit(0)
