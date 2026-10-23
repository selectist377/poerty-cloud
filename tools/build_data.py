#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并五个批次为 data/poems_source.json，并做跨批次唯一性检查。"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
BATCH_DIR = BASE / "data" / "batches"
OUT = BASE / "data" / "poems_source.json"
EXPECT = 100


def main() -> int:
    poems = []
    for i in range(1, 6):
        path = BATCH_DIR / f"batch{i}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        batch_poems = data["poems"]
        print(f"batch{i}: {len(batch_poems)} 首（{data.get('theme', '')}）")
        for p in batch_poems:
            p["batch"] = i
        poems.extend(batch_poems)

    poems.sort(key=lambda p: p["poem_id"])
    ids = Counter(p["poem_id"] for p in poems)
    titles = Counter(p["title"] for p in poems)
    lines = Counter(ln for p in poems for ln in p["lines"])
    problems = []
    if len(poems) != EXPECT:
        problems.append(f"诗稿总数为 {len(poems)}，应为 {EXPECT}")
    for pid, n in ids.items():
        if n > 1:
            problems.append(f"poem_id 重复：{pid}×{n}")
    for t, n in titles.items():
        if n > 1:
            problems.append(f"标题重复：{t}×{n}")
    for ln, n in lines.items():
        if n > 1:
            problems.append(f"诗句重复：{ln}×{n}")
    if problems:
        print("发现问题：")
        for x in problems:
            print("  -", x)
        return 1

    out = {
        "meta": {
            "protocol": "诗云 v3.9",
            "generated_at": "2026-10-23",
            "total": len(poems),
            "batches": 5,
            "per_batch": 20,
            "note": "三节十二行；A 类 14-18 字，B 类两短句各 8-10 字。",
        },
        "poems": poems,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写入 {OUT.relative_to(BASE)}：{len(poems)} 首，"
          f"共 {sum(len(p['lines']) for p in poems)} 行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
