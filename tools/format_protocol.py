#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把协议原稿整理为 80 列等宽排版版，并修正原稿中的三处内部矛盾：

1. 第 8.3 节残留 v3.8 的“建议 15-20 次”频次口径，与 v3.9 取消虚词配额冲突；
2. 第十三节末尾残留 v3.8 的“的≤3 / 时体词 1-5 / N 稳定 90”旧规则；
3. NLP 自然度诊断分与五维总分同记为 N，造成符号冲突，统一为 N_d 与 N。

用法：python3 tools/format_protocol.py
"""
from __future__ import annotations

import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SRC = BASE / "tools" / "protocol_v3.9.raw.txt"
OUT = BASE / "docs" / "protocol_v3.9.txt"

WIDTH = 80
WRAP = 74
INDENT = "    "

FIXES = [
    ("自然度综合分 N：如实际运行了可复核的验证器，可报告 N（0—100）",
     "自然度诊断分 N_d：如实际运行了可复核的验证器，可报告 N_d（0—100）"),
    ("N 应标为“不可复核／未执行”", "N_d 应标为“不可复核／未执行”"),
    ("N 是诊断指标，不等同于文学质量", "N_d 是诊断指标，不等同于文学质量"),
    ("不得把 N≥90 设为最终成稿的独立必要条件", "不得把 N_d≥90 设为最终成稿的独立必要条件"),
    ("N 低于 90 时，应查看分项与问题清单", "N_d 低于 90 时，应查看分项与问题清单"),
    ("N≥90 也不代表自动通过", "N_d≥90 也不代表自动通过"),
    ("N 的分数阈值尚未完成独立校准", "N_d 的分数阈值尚未完成独立校准"),
    ("第一，N 的计算须可复现", "第一，N_d 的计算须可复现"),
    ("不得声称 N 已达某个分数", "不得声称 N_d 已达某个分数"),
    ("报告 N 时同时报告工具和分项；N 缺失或不可复现时",
     "报告 N_d 时同时报告工具和分项；N_d 缺失或不可复现时"),
    ("无论 N 高低，同节同一实义词项重复都按 G7 处理；N 的高分",
     "无论 N_d 高低，同节同一实义词项重复都按 G7 处理；N_d 的高分"),
    ("N 的低分也不能单独否决", "N_d 的低分也不能单独否决"),
    ("记录\"了、着、在、过\"的实际语法功能和用例，建议相应词语使用次数为15-20次，但不设每类最低次数。",
     "记录\"了、着、在、过\"的实际语法功能和用例；不设每类必需次数，也不因未出现而判不合格，"
     "出现频率仅作复核提示。"),
    ("若运行 NLP，须报告 N 及其可复核性；N 不单独决定交付状态。",
     "若运行 NLP，须报告 N_d 及其可复核性；N_d 不单独决定交付状态。"),
    ("N 作为诊断指标报告，不设未经校准的 90 分硬门槛。",
     "N_d 作为诊断指标报告，不设未经校准的 90 分硬门槛。"),
    ("同时报告 NLP 自然度诊断分 N（0—100，见第 6.4 节",
     "同时报告 NLP 自然度诊断分 N_d（0—100，见第 6.4 节"),
    ("N 不纳入 Q 的公式", "N_d 不纳入 Q 的公式"),
    ("Q 与 N 共同提供文本层面的不同诊断视角", "Q 与 N_d 共同提供文本层面的不同诊断视角"),
    ("若运行 NLP，须报告 N、工具配置与分项依据，但 N 不单独决定",
     "若运行 NLP，须报告 N_d、工具配置与分项依据，但 N_d 不单独决定"),
]

OLD_PROMPT_PARA = (
    "用词须尽可能避免重复：同一节内任何二字及以上词项只出现一次，禁用顶针式首尾相接，"
    "不用\"那些／许多\"等泛指标记凑字；连贯性改用贯穿全诗的单字线索（如\"也\"）实现，"
    "单字豁免重复检查。虚词自然度须做到满分——\"的\"≤3、时体词\"了着在过\"总量 1—5 且以\"了\"为主、"
    "相邻两词不得同为虚词。把同节重复、语意跳跃、虚词相邻、时体词过量、代词过量、\"的\"过量六类问题全部清零，"
    "使 N 稳定达到 90 以上（具体见第 6.5 节）。"
)
NEW_PROMPT_PARA = (
    "用词须尽可能避免重复：同一节内任何二字及以上实义词项只出现一次，禁用顶针式首尾相接，"
    "不用\"那些／许多\"等泛指标记凑字；语意连贯须由具体文本关系、动作、因果、感官或结构回照支撑，"
    "单字线索只是可选技法，不因共享字形自动认定连贯。虚词不设配额，逐处按实际语法功能判断，"
    "不得为凑字数删去必要的\"的、地、得、了、着、过\"或必要介词，也不得机械添入。"
    "同节实义词项重复、无依据的语意跳跃、必要虚词缺失、代词超限四类硬性问题必须清零；"
    "N_d 作为 NLP 诊断指标如实报告，不设未经校准的 90 分硬门槛；N 分只作质量分层，不得替代 G1—G10。"
)

KEY_BOXES = [
    "形式合格不能补偿病句，审美判断不能抵消硬性错误",
    "N 高不能抵消硬性错误，N 低也不能单独否决作品",
    "同一节内同一实义词项不得重复",
    "不得为达标写出病句",
]

CHAPTER_RE = re.compile(r"^[一二三四五六七八九十]+、")
SECTION_RE = re.compile(r"^\d+\.\d+\s")


def is_chapter(text: str) -> bool:
    if not CHAPTER_RE.match(text):
        return False
    plain = text.replace("NLP", "").replace("A／B", "")
    if "。" in plain or "：" in plain:
        return False
    if re.search(r"[A-Za-z]{2,}", plain):
        return False
    return dwidth(text) <= 66


def dwidth(text: str) -> int:
    return sum(2 if "\u4e00" <= ch <= "\u9fff" else 1 for ch in text)


def pad(text: str, width: int) -> str:
    return text + " " * max(0, width - dwidth(text))


def center(text: str, width: int = WIDTH) -> str:
    gap = max(0, width - dwidth(text))
    left = gap // 2
    return " " * left + text


def wrap(text: str, width: int = WRAP) -> list:
    """按显示宽度折行；把连续的 ASCII 片段当作不可拆分的整体。"""
    import re as _re
    tokens = _re.findall(r"[A-Za-z0-9_./:%+\-]+|\s+|.", text)
    out, cur, cur_w = [], "", 0
    for tok in tokens:
        w = dwidth(tok)
        if cur_w + w > width and cur:
            if tok in "，。、；：？！）》”’·":
                cur += tok
                out.append(cur)
                cur, cur_w = "", 0
                continue
            out.append(cur.rstrip())
            cur, cur_w = "", 0
        if tok.isspace():
            if cur:
                cur += " "
                cur_w += 1
            continue
        cur += tok
        cur_w += w
    if cur:
        out.append(cur.rstrip())
    return out or [""]


def boxed(paragraph: str) -> list:
    inner_w = WIDTH - 4
    body = wrap(paragraph, inner_w - 2)
    lines = ["┌" + "─" * (WIDTH - 2) + "┐"]
    for b in body:
        lines.append("│ " + b + " " * max(0, inner_w - dwidth(b)) + " │")
    lines.append("└" + "─" * (WIDTH - 2) + "┘")
    return lines


def main() -> int:
    raw = SRC.read_text(encoding="utf-8").split("\n")
    # 跳过原有标题块与目录块：以正文中第二次出现的“一、适用范围”为起点
    starts = [i for i, ln in enumerate(raw) if ln.strip().startswith("一、适用范围")]
    body = raw[starts[-1]:] if starts else raw[6:]

    text = "\n".join(body)
    for old, new in FIXES:
        if old not in text:
            print(f"[warn] 未找到待修正片段：{old[:28]}…")
        text = text.replace(old, new)
    if OLD_PROMPT_PARA in text:
        text = text.replace(OLD_PROMPT_PARA, NEW_PROMPT_PARA)
    else:
        print("[warn] 第十三节旧版提示词段落未精确匹配，改按行定位")
        lines = text.split("\n")
        for i, ln in enumerate(lines):
            if "虚词自然度须做到满分" in ln:
                lines[i] = NEW_PROMPT_PARA
        text = "\n".join(lines)

    paragraphs = [ln.strip() for ln in text.split("\n") if ln.strip()]

    # 先建立目录
    chapters = [p for p in paragraphs if is_chapter(p)]
    toc = ["目　录", ""]
    for ch in chapters:
        dots = "." * max(3, WIDTH - 4 - dwidth(ch) - 2)
        toc.append("  " + ch + " " + dots)
    for p_ in paragraphs:
        if p_.startswith("附录"):
            dots = "." * max(3, WIDTH - 4 - dwidth(p_) - 2)
            toc.append("  " + p_ + " " + dots)
    toc.append("")

    out = []
    out.append("█" * WIDTH)
    out.append("")
    out.append(center("诗　云　v3.9"))
    out.append(center("十二行生成式诗歌写作协议"))
    out.append(center("八轮筛查 · 反向审计 · 形式核验 · 关联判定 · 增量审计 · 回归验证"))
    out.append("")
    out.append("─" * (WIDTH - 2))
    meta = [
        ("版本", "v3.9"),
        ("日期", "2026 年 10 月 23 日"),
        ("语言", "简体中文"),
        ("适用", "AI 辅助创作、单篇验收、协议版本实验"),
        ("性质", "内部工作规范"),
        ("声明", "请勿作为已独立验证的方法论引用"),
    ]
    for k, v in meta:
        out.append("  " + pad(k + "：", 12) + v)
    out.append("─" * (WIDTH - 2))
    out.append("")
    out.extend(toc)
    out.append("█" * WIDTH)
    out.append("")

    boxed_keys = set()
    for para in paragraphs:
        if is_chapter(para):
            out.append("")
            out.append("═" * WIDTH)
            out.append(center(para))
            out.append("═" * WIDTH)
            out.append("")
            continue
        if SECTION_RE.match(para):
            title = " " + para + " "
            out.append("")
            out.append("────" + title + "─" * max(2, WIDTH - 4 - dwidth(title)))
            out.append("")
            continue
        if (para.startswith("版本变更说明") or
                (para.startswith("历史版本变更记录") and len(para) < 40)):
            out.append("")
            out.append("▓" * WIDTH)
            out.append(center(para))
            out.append("▓" * WIDTH)
            out.append("")
            continue
        if para.startswith("附录"):
            out.append("")
            out.append("═" * WIDTH)
            out.append(center(para))
            out.append("═" * WIDTH)
            out.append("")
            continue

        box_key = next((k for k in KEY_BOXES if k in para and k not in boxed_keys), None)
        if box_key:
            boxed_keys.add(box_key)
            out.extend(boxed(para))
            out.append("")
            continue

        for i, line in enumerate(wrap(para)):
            out.append(INDENT + line)
        out.append("")

    # 本仓库校订记录
    out.append("")
    out.append("═" * WIDTH)
    out.append(center("附录二　本仓库 v3.9 校订记录"))
    out.append("═" * WIDTH)
    out.append("")
    notes = [
        "一、第 6.4 节与第 15.3 节原将 NLP 自然度诊断分与五维去极值总分同记为 N，"
        "造成同一符号两种口径。本版统一：五维总分记 N，NLP 自然度诊断分记 N_d，"
        "并在第 6.4、6.5、12、13、15.3、15.5 节同步改写。",
        "二、第 8.3 节残留“建议相应词语使用次数为 15-20 次”的 v3.8 频次口径，"
        "与 v3.9 取消虚词配额相冲突，已改为“不设每类必需次数，出现频率仅作复核提示”。",
        "三、第十三节末尾残留 v3.8 的“的≤3、时体词 1—5、六类问题清零、N 稳定 90 以上”"
        "旧规则，与正文第 6.1、6.5 节冲突，已改写为 v3.9 口径：虚词按语法功能逐处判断，"
        "N_d 为诊断指标，N 只作质量分层。",
        "四、原稿目录与正文标题存在层级混排，本版重排为章（一、二、三……）、"
        "节（1.1、1.2……）两级，并以 80 列等宽网格对齐。",
        "五、以上校订只处理内部矛盾与排版，不改变任何硬性门槛、评分权重或验收线。",
    ]
    for note in notes:
        for line in wrap(note):
            out.append(INDENT + line)
        out.append("")

    out.append("█" * WIDTH)
    out.append(center("—— 协议全文终 ——"))
    out.append("█" * WIDTH)
    out.append("")

    # 行宽校验
    for i, line in enumerate(out, 1):
        if dwidth(line) > WIDTH:
            print(f"[warn] 第 {i} 行超宽（{dwidth(line)} 列）：{line[:40]}")

    OUT.write_text("\n".join(out), encoding="utf-8", newline="\n")
    print(f"已生成 {OUT.relative_to(BASE)}：{len(out)} 行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
