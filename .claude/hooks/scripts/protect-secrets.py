#!/usr/bin/env python3
"""PreToolUse hook for Write|Edit: blocks writing hardcoded secrets or editing .env directly."""
import json, re, sys

try:
    data = json.load(sys.stdin)
    ti = data.get("tool_input") or {}
    path = ti.get("file_path") or ti.get("path") or ""
    content = ti.get("content") or ti.get("new_string") or ti.get("new_str") or ""
except Exception:
    sys.exit(0)

# .env.example разрешён, реальные .env — нет
if re.search(r"(^|/)\.env(\.(local|production|prod|staging|development|dev))?$", path):
    print("Blocked: do not write real .env files. Update .env.example with placeholder values and tell the user which secrets to set.", file=sys.stderr)
    sys.exit(2)

SECRET_PATTERNS = [
    (r"sk-[A-Za-z0-9]{20,}", "OpenAI-style secret key"),
    (r"sk-ant-[A-Za-z0-9-]{20,}", "Anthropic API key"),
    (r"ghp_[A-Za-z0-9]{30,}", "GitHub token"),
    (r"AKIA[0-9A-Z]{16}", "AWS access key"),
    (r"-----BEGIN\s+(RSA|EC|OPENSSH|DSA)?\s*PRIVATE KEY-----", "private key"),
    (r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b", "Telegram bot token"),
    (r"(password|passwd|secret|api[_-]?key|token)\s*[:=]\s*[\"'][^\"'\s]{16,}[\"']", "hardcoded credential"),
]
skip = re.search(r"(\.example|\.md|test|spec|fixture)", path, re.IGNORECASE)
if not skip:
    for pat, name in SECRET_PATTERNS:
        m = re.search(pat, content)
        if m:
            print(f"Blocked: looks like a hardcoded {name} in {path}. Load secrets from environment variables (validated config) instead.", file=sys.stderr)
            sys.exit(2)
sys.exit(0)
