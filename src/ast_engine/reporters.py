from __future__ import annotations

import json
from collections import Counter

from ast_engine.models import Finding


def text_report(findings: list[Finding]) -> str:
    if not findings:
        return "No issues found."
    lines = [str(f) for f in findings]
    counts = Counter(f.code for f in findings)
    summary = ", ".join(f"{code}: {n}" for code, n in sorted(counts.items()))
    lines.append(f"\nFound {len(findings)} issue(s) ({summary}).")
    return "\n".join(lines)


def json_report(findings: list[Finding]) -> str:
    return json.dumps([f.to_dict() for f in findings], indent=2)


REPORTERS = {"text": text_report, "json": json_report}
