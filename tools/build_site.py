#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""由诗稿数据与评分数据生成静态站点 index.html（零外部依赖、可离线双击打开）。"""
from __future__ import annotations

import html
import json
import statistics
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data" / "poems_source.json"
SCORES = BASE / "scripts" / "raw_scores.json"
OUT = BASE / "index.html"

sys.path.insert(0, str(BASE / "scripts"))
from generate_final import BATCH_NAMES, DIM_NAMES, DIMS, RATERS, compute_n, gate_check  # noqa: E402

SEAL_TEXT = "N≥90"


def esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def render_card(poem: dict, dims: dict, total: float, index: int) -> str:
    seal_text = "N≥90" if total >= 90 else f"N {total:.1f}"
    seal_cls = "seal" if total >= 90 else "seal seal-soft"
    pid = poem["poem_id"]
    anchor = f"p{index:03d}"
    lines = "\n".join(f'<span class="line">{esc(x)}</span>' for x in poem["lines"])
    score_bits = "".join(
        f'<span class="score"><em>{d}</em><b>{dims[d]:.1f}</b></span>' for d in DIMS
    )
    return f"""      <article class="poem-card">
        <input class="poem-toggle" type="checkbox" id="{anchor}" aria-label="展开{esc(poem['title'])}">
        <label class="poem-head" for="{anchor}">
          <span class="poem-no">{esc(pid)}</span>
          <span class="{seal_cls}" aria-hidden="true">{seal_text}</span>
          <h3 class="poem-title">{esc(poem['title'])}</h3>
          <p class="poem-summary">{esc(poem['summary'])}</p>
          <span class="poem-meta">{esc(BATCH_NAMES[poem['batch']])} · 总分 {total:.1f}</span>
          <span class="poem-more"><span class="more-open">展开全文</span><span class="more-close">收起全文</span></span>
        </label>
        <div class="poem-body">
          <div class="poem-text">
{lines}
          </div>
          <div class="poem-scores">
            {score_bits}
          </div>
          <div class="poem-foot">情感核心：{esc(poem['emotion']['core'])}</div>
        </div>
      </article>"""


def main() -> int:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    poems = data["poems"]
    score_map = {s["poem_id"]: s for s in json.loads(SCORES.read_text(encoding="utf-8"))["poems"]}

    rows = []
    for poem in poems:
        agg = compute_n(score_map[poem["poem_id"]]["scores"])
        dims = {d: round(v, 1) for d, v in agg["dims"].items()}
        total = round(agg["N"], 1)
        admitted = all(v >= 15 for v in dims.values()) and all(
            v[0] for v in gate_check(poem).values()
        )
        rows.append((poem, dims, total, admitted))

    admitted_rows = [r for r in rows if r[3]]
    totals = [r[2] for r in admitted_rows]
    cards = "\n".join(render_card(p, d, t, i + 1) for i, (p, d, t, _ok) in enumerate(admitted_rows))

    stat = {
        "poems": len(admitted_rows),
        "candidates": len(rows),
        "avg": statistics.mean(totals),
        "max": max(totals),
        "min": min(totals),
        "n90": sum(1 for t in totals if t >= 90),
        "n90_pct": sum(1 for t in totals if t >= 90) / len(totals) * 100,
        "raters": len(RATERS),
        "gates": 10,
    }

    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>诗云 Poetry Cloud · 十二行生成式诗歌协议 v3.9</title>
  <meta name="description" content="诗云 v3.9：三节十二行的现代汉语诗歌写作协议。100 首盲测终稿、五代理五维评分、八轮筛查与可复核审计。">
  <meta name="theme-color" content="#F9F7F1">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <a class="skip-link" href="#poems">跳到诗歌</a>

  <header class="hero" id="top">
    <div class="hero-frame">
      <p class="hero-kicker">十二行生成式诗歌写作协议</p>
      <h1 class="hero-title">诗云</h1>
      <p class="hero-en">POETRY&nbsp;CLOUD</p>
      <p class="hero-rule"><span></span>V 3 . 9<span></span></p>
      <p class="hero-desc">三节十二行 · 八轮筛查 · 五维盲测 · 可复核审计</p>
      <p class="hero-date">二〇二六年十月二十三日</p>
    </div>
    <div class="hero-mountain" aria-hidden="true"></div>
  </header>

  <main>
    <section class="section" id="about">
      <div class="section-head">
        <span class="section-index">壹</span>
        <h2>项目简介</h2>
      </div>
      <div class="prose">
        <p>诗云是一份面向现代汉语的<strong>固定形式写作协议</strong>：正文严格三节、每节四行、共十二行，A 类行为 14–18 字的单一完整长句，B 类行由两个 8–10 字的短句以一个空格分隔。形式不是目的，而是让语言在压力下暴露问题的量具。</p>
        <p>v3.9 把 v3.8 的“N≥90 一票否决”降级为<strong>辅助诊断指标</strong>，取消虚词的机械配额，改以实际语法功能判断；同节实义词项去重仍是硬性门槛。硬性门槛负责作品是否成立，盲测评分负责质量分层，二者互不抵消。</p>
      </div>
      <div class="pillars">
        <div class="pillar"><b>形式核验</b><span>十二行、A/B 行式、逐字计数，任何改动都使旧计数失效。</span></div>
        <div class="pillar"><b>八轮筛查</b><span>词项、语法、结构、节奏、美学、可进入性、流程合规、压力测试。</span></div>
        <div class="pillar"><b>盲测评分</b><span>R1–R5 背靠背独立打分，去极值后取均值，五维合成 N 分。</span></div>
      </div>
    </section>

    <section class="section" id="protocol">
      <div class="section-head">
        <span class="section-index">贰</span>
        <h2>协议要点</h2>
      </div>
      <div class="protocol-grid">
        <div class="protocol-block">
          <h3>形式约束</h3>
          <ul>
            <li>三节十二行，每节四行，无题记与尾声。</li>
            <li>A 类：14–18 字，单一完整句，行内无标点。</li>
            <li>B 类：两个 8–10 字短句，仅一个半角空格分隔。</li>
            <li>每节至少一行 A、一行 B；不得连续两行 A。</li>
          </ul>
        </div>
        <div class="protocol-block">
          <h3>硬性门槛 G1–G10</h3>
          <ul>
            <li>行数、行式、字数、句界、语法。</li>
            <li>代词单字化与频次，名词核心与一字名词准入。</li>
            <li>同节实义词项不得重复，复合词语素另行审查。</li>
            <li>转折标记每节不超过一个，拒绝模板化反转。</li>
          </ul>
        </div>
        <div class="protocol-block">
          <h3>评分与筛选</h3>
          <ul>
            <li>IR 意象 / MH 音韵 / SD 语义 / SI 结构 / II 创新。</li>
            <li>每维 0–20 分，去掉最高最低后取中间三个均值。</li>
            <li>五维均值求和为 N，满分 100。</li>
            <li>准入：G=10 且五维单项均 ≥15；N≥90 仅作诊断。</li>
          </ul>
        </div>
      </div>
      <p class="note">协议全文：<a href="docs/protocol_v3.9.txt">docs/protocol_v3.9.txt</a> · 盲测报告：<a href="docs/blind_test_report_N90.txt">docs/blind_test_report_N90.txt</a> · 终稿诗集：<a href="docs/poetry_collection_final.txt">docs/poetry_collection_final.txt</a></p>
    </section>

    <section class="section" id="stats">
      <div class="section-head">
        <span class="section-index">叁</span>
        <h2>数据成果</h2>
      </div>
      <div class="stats">
        <div class="stat"><b>{stat['poems']}</b><span>终稿首数</span></div>
        <div class="stat"><b>{stat['avg']:.2f}</b><span>平均总分 N</span></div>
        <div class="stat"><b>{stat['max']:.1f}</b><span>最高分</span></div>
        <div class="stat"><b>{stat['min']:.1f}</b><span>最低分</span></div>
        <div class="stat"><b>{stat['raters']}</b><span>评审代理</span></div>
        <div class="stat"><b>{stat['gates']}/10</b><span>硬性门槛</span></div>
      </div>
      <div class="stats-note">
        <p>候选 {stat['candidates']} 首，通过 G1–G10 且五维单项均 ≥15 者 {stat['poems']} 首；其中 N≥90 者 {stat['n90']} 首。依据 v3.9，N≥90 是辅助诊断标签，不构成入选与否的一票否决条件。</p>
        <p>评分属 <strong>E1 内部盲测（模型评审）</strong>：五个评审配置按公开权重独立打分，可复现但不等同人工评审或外部验证。第八轮采用路径 B 结构化压力测试，多作品比对未完成。</p>
      </div>
    </section>

    <section class="section section-poems" id="poems">
      <div class="section-head">
        <span class="section-index">肆</span>
        <h2>盲测诗歌</h2>
        <p class="section-sub">点按卡片展开全文与五维得分</p>
      </div>
      <div class="poem-grid">
{cards}
      </div>
    </section>

    <section class="section" id="limits">
      <div class="section-head">
        <span class="section-index">伍</span>
        <h2>方法与局限</h2>
      </div>
      <div class="prose">
        <p>本仓库的分数仅用于同一协议内的定位与版本比较，不是文学质量刻度。所有硬性门槛判定都要求落到具体行次与文本证据；没有证据的通过一律降为“待核实”。</p>
        <p>形式全部通过而整体评价落后的情况并不罕见，因此本页把<strong>形式通过率</strong>与<strong>整体评价</strong>分开呈现。协议与盲测均未经过独立人工实验验证，读者不应把此处数据当作方法论有效性的证明。</p>
      </div>
    </section>
  </main>

  <footer class="footer">
    <p class="footer-title">诗云 Poetry Cloud</p>
    <p>诗歌文本采用 <a href="LICENSE">CC BY-NC 4.0</a> 授权；脚本代码可采用 MIT 授权。</p>
    <p class="footer-links">
      <a href="README.md">README</a>
      <a href="docs/protocol_v3.9.txt">写作协议</a>
      <a href="docs/blind_test_report_N90.txt">盲测报告</a>
      <a href="docs/poetry_collection_final.txt">终稿诗集</a>
      <a href="docs/certificate_v3.9.txt">证书</a>
      <a href="scripts/generate_final.py">生成脚本</a>
    </p>
    <p class="footer-fine">内部工作规范 · 不宣称已通过独立实验验证 · 二〇二六</p>
  </footer>
</body>
</html>
"""
    assert page.count('<span class="more-open">展开全文</span>') == len(admitted_rows), "展开全文出现次数异常"
    assert page.count('<span class="more-close">收起全文</span>') == len(admitted_rows), "收起全文出现次数异常"
    OUT.write_text(page, encoding="utf-8", newline="\n")
    print(f"已生成 {OUT.relative_to(BASE)}：{len(admitted_rows)} 张诗卡，平均 N {stat['avg']:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
