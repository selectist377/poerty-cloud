#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用实际统计替换 README 中的占位符。"""
import json, re, statistics, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from generate_final import compute_n, gate_check  # noqa: E402

data = json.loads((BASE / "data" / "poems_source.json").read_text(encoding="utf-8"))
poems = data["poems"]
scores = {s["poem_id"]: s for s in json.loads((BASE / "scripts" / "raw_scores.json").read_text(encoding="utf-8"))["poems"]}
totals, admitted = [], 0
for p in poems:
    agg = compute_n(scores[p["poem_id"]]["scores"])
    dims = [round(v, 1) for v in agg["dims"].values()]
    ok = all(v[0] for v in gate_check(p).values())
    if ok and all(d >= 15 for d in dims):
        admitted += 1
        totals.append(round(agg["N"], 1))
text = (BASE / "README.md").read_text(encoding="utf-8")
text = (text.replace("{{TOTAL}}", str(len(poems)))
        .replace("{{ADMITTED}}", str(admitted))
        .replace("{{AVG}}", f"{statistics.mean(totals):.2f}")
        .replace("{{MAX}}", f"{max(totals):.1f}")
        .replace("{{MIN}}", f"{min(totals):.1f}")
        .replace("{{N90}}", str(sum(1 for t in totals if t >= 90))))
(BASE / "README.md").write_text(text, encoding="utf-8", newline="\n")
print("README 已填充：", len(poems), "首，入选", admitted, "平均", round(statistics.mean(totals), 2))
