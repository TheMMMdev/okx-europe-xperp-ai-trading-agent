from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_TRACKED = (
    re.compile(r"(^|/)\.env($|\.)"),
    re.compile(r"(^|/)(logs|backups)/"),
    re.compile(r"^data/.*\.(db|sqlite|sqlite3|enc|key|log|jsonl|xlsx|csv|bak)$"),
    re.compile(r"^data/\.astra_"),
)
SECRET_ASSIGNMENT = re.compile(
    r"(?im)^[ \t]*(OKX_(?:LIVE|DEMO)?_?(?:API_KEY|SECRET_KEY|PASSPHRASE)|LLM_API_KEY|"
    r"ASTRA_ADMIN_TOKEN|ASTRA_SETUP_TOKEN)[ \t]*=[ \t]*([^\s#][^\r\n]*)$"
)
PLACEHOLDERS = ("your_", "replace_", "example", "test", "demo_", "live_", "<", "${")


def tracked_files() -> list[str]:
    result = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                            cwd=ROOT, text=True, capture_output=True, check=True)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    failures: list[str] = []
    tracked = tracked_files()
    for rel in tracked:
        normalized = rel.replace("\\", "/")
        if normalized == "data/prompt_library.json":
            continue
        if any(pattern.search(normalized) for pattern in FORBIDDEN_TRACKED):
            failures.append(f"tracked runtime/sensitive path: {normalized}")
        path = ROOT / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for match in SECRET_ASSIGNMENT.finditer(text):
            if normalized.startswith("tests/"):
                continue
            value = match.group(2).strip().strip('"').strip("'")
            if value and not any(marker in value.lower() for marker in PLACEHOLDERS):
                failures.append(f"possible committed credential: {normalized}:{text[:match.start()].count(chr(10)) + 1}")
    required = {
        "README.md": ("EEA X-Perp support", "Referral and broker compensation", "Known limitations"),
        "env.example": ("ASTRA_XPERP_EXECUTION=0", "OKX_INVITE_URL=", "OKX_BROKER_TAG="),
        ".gitignore": (".env", "data/*.enc", "logs/", "backups/"),
    }
    for rel, markers in required.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                failures.append(f"missing release marker {marker!r} in {rel}")
    if "DEFAULT_OKX_BROKER_TAG = \"\"" not in (ROOT / "scripts" / "okx_rest.py").read_text(encoding="utf-8"):
        failures.append("default broker tag must remain empty")
    if failures:
        print("Release preflight failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"Release preflight passed: {len(tracked)} tracked files checked; no tracked secrets/runtime data found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
