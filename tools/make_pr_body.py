#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按实际数据生成 docs/PR_BODY.md（发布前调用）。"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from generate_final import compute_n, gate_check, RATERS  # noqa: E402

data = json.loads((BASE / "data" / "poems_source.json").read_text(encoding="utf-8"))
poems = data["poems"]
scores = {s["poem_id"]: s for s in json.loads(
    (BASE / "scripts" / "raw_scores.json").read_text(encoding="utf-8"))["poems"]}

totals, admitted, g_all = [], 0, 0
for p in poems:
    agg = compute_n(scores[p["poem_id"]]["scores"])
    dims = [round(v, 1) for v in agg["dims"].values()]
    gates = gate_check(p)
    ok = all(v[0] for v in gates.values())
    g_all += ok
    if ok and all(d >= 15 for d in dims):
        admitted += 1
        totals.append(round(agg["N"], 1))
n90 = sum(1 for t in totals if t >= 90)

body = f"""# 诗云 v3.9：协议校订、{len(poems)} 首终稿、五代理盲测与静态站点

## 概述

本 PR 按《诗云 v3.9 十二行生成式诗歌写作协议》与配套研究方案，交付完整项目：协议排版校订版、{len(poems)} 首三节十二行诗稿、五代理五维盲测评分、G1–G10 逐首核验、盲测报告、终稿诗集、证书、静态展示页与可复现脚本。

## 对源文件的校订

- **P1 符号冲突**：第 6.4 / 15.3 节把 NLP 自然度诊断分与五维总分同记为 `N`。本版统一为五维总分 `N`、NLP 诊断分 `N_d`，并在 6.5、12、13、15.3、15.5 节同步改写。
- **P2 配额残留**：第 8.3 节仍写“建议相应词语使用次数为 15-20 次”，与 v3.9 取消虚词配额冲突，改为“不设每类必需次数，出现频率仅作复核提示”。
- **P3 旧版提示词**：第十三节末尾残留 v3.8 的“的≤3、时体词 1—5、N 稳定 90 以上”，与正文冲突，改写为 v3.9 口径。
- **P4 目录层级**：原稿目录与正文标题层级混排，重排为 80 列等宽的两级目录。
- **研究方案校订**：方案第 3.5 节把 `N≥90` 列为入选条件，与 v3.9 的辅助诊断定位冲突，本仓库按 `G=10 且五维单项≥15` 准入；方案第 3.4 节的 G 编号与协议不一致，统一采用协议第 15.1 节编号。

详见 `docs/research_notes.md` 与协议附录二。

## 交付物

| 文件 | 说明 |
| --- | --- |
| `docs/protocol_v3.9.txt` | 协议 80 列排版校订版（{sum(1 for _ in open(BASE / 'docs' / 'protocol_v3.9.txt', encoding='utf-8'))} 行） |
| `data/poems_source.json` | {len(poems)} 首候选诗正文 |
| `scripts/raw_scores.json` | R1–R5 × 五维原始评分 |
| `scripts/generate_final.py` | 门槛核验、去极值聚合、报告/诗集/证书生成（仅标准库） |
| `docs/blind_test_report_N90.txt` | 盲测报告（逐条明细、统计、一致性、规格博弈审计） |
| `docs/poetry_collection_final.txt` | 终稿诗集 |
| `docs/certificate_v3.9.txt` | 认证证书 |
| `docs/gate_matrix.txt` | G1–G10 逐首核验矩阵 |
| `docs/pressure_test_log.md` | 第八轮路径 B 压力测试记录 |
| `index.html` / `style.css` | 零外部依赖的静态展示页 |

## 数据

- 候选诗稿：{len(poems)} 首（五批次）
- 通过 G1–G10：{g_all} 首
- 准入（G=10 且五维单项≥15）：{admitted} 首
- 平均总分 N：{statistics.mean(totals):.2f}；最高 {max(totals):.1f}；最低 {min(totals):.1f}
- N≥90：{n90} 首（辅助诊断，不作为否决条件）

## 验证

```
$ python3 tools/validate_poems.py data/poems_source.json --strict
合计 {len(poems)} 首，失败 0 首。

$ python3 scripts/generate_final.py
候选 {len(poems)} 首；入选 {admitted} 首；G=10 共 {g_all} 首
```

## 方法与边界

- 评分属 **E1 内部盲测（模型评审）**：五个评审配置按公开权重独立打分，可复现，但不等同人工评审或外部验证。
- 第八轮采用 **路径 B 结构化压力测试**，多作品比对未完成；未做外部人工盲评与真实读者实验。
- 本仓库不宣称协议已通过独立实验验证，也不把分数当作文学质量刻度。

## 部署

合并后开启 GitHub Pages（main 分支根目录），页面为 `index.html`，无构建步骤、无外部依赖。
"""
(BASE / "docs" / "PR_BODY.md").write_text(body, encoding="utf-8", newline="\n")
print("PR body written:", len(body), "chars")
