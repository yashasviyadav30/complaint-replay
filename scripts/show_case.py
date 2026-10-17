"""Print one real-bug benchmark result in a few lines: stage, proof, fix files and errors, guard, every step.

    gh run download <run id> --repo yashasviyadav30/complaint-replay -n case-<pr> -D <dir>
    uv run python scripts/show_case.py <dir>/real-bugs/pr<pr>.json
"""

import json
import sys

case = json.load(open(sys.argv[1], encoding="utf-8"))
replay, fix = case.get("replay", {}), case.get("fix", {})
print("stage", case.get("stage"), "| steps", len(replay.get("steps", [])), "|", (replay.get("summary") or "")[:220])
for e in replay.get("evidence", []):
    if e["id"] in replay.get("cited", []):
        print("  cited", e["kind"], e["detail"][:170])
print("  fix files", sorted({e.get("file") for e in (fix.get("edits") or [])}), "| errors", fix.get("errors"))
if fix.get("shown"):
    real = case.get("bench", {}).get("real_files", [])
    print("  shown", len(fix["shown"]), "files | real fix file shown:", [f in fix["shown"] for f in real])
print("  explanation", (fix.get("explanation") or "")[:250])
print("  guard", {k: v for k, v in case.get("guard", {}).items() if k in ("passes_on_fix", "catches_bug")})
for s in replay.get("steps", []):
    a = s["action"]
    print("   ", a.get("type"), a.get("key", ""), a.get("times", ""), a.get("text", ""), "|",
          (s.get("target") or "")[:45], "->", s["result"][:70])
