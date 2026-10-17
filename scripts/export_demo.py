"""Copy real recorded cases (and their screenshots and films) into the dashboard's static demo folder."""

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "results" / "cases"
DEMO = ROOT / "dashboard" / "public" / "demo"


def main() -> None:
    shutil.rmtree(DEMO, ignore_errors=True)
    (DEMO / "shots").mkdir(parents=True)
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in CASES.glob("*.json")]
    cases.sort(key=lambda c: c.get("created_at", ""), reverse=True)
    for case in cases:
        for name in [*(case.get("shots") or {}).values(), *(case.get("films") or {}).values()]:
            if (CASES / "shots" / name).exists():
                shutil.copy2(CASES / "shots" / name, DEMO / "shots" / name)
    (DEMO / "cases.json").write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    print(f"exported {len(cases)} cases")


if __name__ == "__main__":
    main()
