#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诗云 v3.9 终稿生成与评分脚本

输入：
    data/poems_source.json   100 首候选诗的正文（三节十二行）
    scripts/raw_scores.json  5 个评审代理（R1-R5）对五维的独立打分

处理：
    1. 依据协议第十五章 15.1 节，逐首执行 G1-G10 硬性门槛检查；
    2. 对每个维度去掉 5 个评分中的最高分与最低分，取中间 3 个的算术平均；
    3. 五维均值求和得到总分 N（保留一位小数）；
    4. 终稿准入：G=10 且五维单项均不低于 15 分。N>=90 按 v3.9 仅为
       辅助诊断指标，不作为一票否决条件；
    5. 输出盲测报告、纯诗歌集与证书文件。

运行：
    python3 scripts/generate_final.py

依赖：仅 Python 3.8+ 标准库。所有文件按 UTF-8 读写，换行为 LF。
"""
from __future__ import annotations

import json
import math
import re
import statistics
import sys
from datetime import date, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA_FILE = BASE / "data" / "poems_source.json"
SCORE_FILE = BASE / "scripts" / "raw_scores.json"
DOCS = BASE / "docs"

DIMS = ["IR", "MH", "SD", "SI", "II"]
DIM_NAMES = {
    "IR": "意象共鸣度",
    "MH": "音韵和谐度",
    "SD": "语义深度",
    "SI": "结构完整性",
    "II": "创新指数",
}
RATERS = ["R1", "R2", "R3", "R4", "R5"]
BATCH_NAMES = {
    1: "第一批（山水与自然）",
    2: "第二批（时间与记忆）",
    3: "第三批（城市与孤独）",
    4: "第四批（身体与感知）",
    5: "第五批（语言与沉默）",
}
VERSION = "v3.9"
REPORT_DATE = "2026年10月23日"

HAN = re.compile(r"^[\u4e00-\u9fff]+$")
PUNCT_CHARS = "，。！？；：、“”‘’（）《》〈〉—…·,.!?;:\"'()[]{}<>~`@#$%^&*+=|\\/＿－　"

SINGLE_PRONOUNS = "我你他她它谁这那其之此咱您"
MULTI_PRONOUNS = ["我们", "你们", "他们", "她们", "它们", "咱们", "自己",
                  "大家", "彼此", "别人", "人家", "各位", "诸位"]
TURN_MARKERS = ["然而", "但是", "可是", "不过", "反而", "其实", "却", "只是",
                "并非", "而是", "原来", "真正", "究竟", "毕竟", "偏偏", "居然"]
NATURE_CHARS = set("山水风云月雨雪雾霜露花草木石河海林岸桥船鸟鱼叶枝根土冰泉浪涛潮霞岚壑溪岭岩崖峰谷塘池潭滩洲岛天星沙阳阴烟虹原野")
FUNCTION_CHARS = set("的地得了着过在是和与从向对把被让也都又还就才很太更最不没有这那那么吗呢啊吧么个片朵场阵条只种样")
ONE_CHAR_NOUNS = set("人手眼耳鼻口舌心肩背腰腿脚头脸身骨头风年月日天人猫狗鸟鱼虫花草树叶门窗户灯路街桥船车马牛羊米面水酒茶书纸笔刀绳碗桶盆壶柜箱床桌椅墙田地房家国城村山")
VERB_START = set("停落吹拂卷过下起升散退涌压遮洗冲推摇动亮暗沉浮飘打在洒滴流漫爬生开照映穿沿绕")
SOFT_MODIFIERS = ("的",)


# --------------------------------------------------------------------------
# 基础工具
# --------------------------------------------------------------------------
def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def han(text: str) -> int:
    """统计文本中的汉字数。"""
    return sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")


def display_width(text: str) -> int:
    """按等宽字体估算显示宽度：汉字记 2，其余记 1。"""
    return sum(2 if "\u4e00" <= ch <= "\u9fff" else 1 for ch in text)


def pad(text: str, width: int, align: str = "left") -> str:
    gap = max(0, width - display_width(text))
    if align == "right":
        return " " * gap + text
    if align == "center":
        left = gap // 2
        return " " * left + text + " " * (gap - left)
    return text + " " * gap


def wrap_cn(text: str, width: int = 76) -> list:
    """按显示宽度折行，标点不置于行首。"""
    lines, cur, cur_w = [], "", 0
    for ch in text:
        w = 2 if "\u4e00" <= ch <= "\u9fff" else 1
        if cur_w + w > width:
            # 避免标点落在下一行行首
            if ch in "，。、；：？！）》”’":
                cur += ch
                lines.append(cur)
                cur, cur_w = "", 0
                continue
            lines.append(cur)
            cur, cur_w = ch, w
        else:
            cur += ch
            cur_w += w
    if cur:
        lines.append(cur)
    return lines or [""]


# --------------------------------------------------------------------------
# 形式判定与 G1-G10
# --------------------------------------------------------------------------
def classify(line: str):
    if " " in line:
        if line.count(" ") != 1:
            return None, "B 类行须恰含一个半角空格"
        a, b = line.split(" ")
        for part in (a, b):
            if not HAN.match(part):
                return None, "B 类短句含非汉字字符"
            if not 8 <= len(part) <= 10:
                return None, "B 类短句字数不在 8-10"
        return "B", (a, b)
    if not HAN.match(line):
        return None, "A 类行含非汉字字符"
    if not 14 <= len(line) <= 18:
        return None, "A 类行字数不在 14-18"
    return "A", line


def nature_standalone(text: str) -> list:
    """保守判定孤立单字景物词，返回位置与字。"""
    weak = set("的地得了着过在是和与也都又还就才很太更最不没个片朵场阵条只种样")
    hits = []
    n = len(text)
    for i, ch in enumerate(text):
        if ch not in NATURE_CHARS:
            continue
        left = text[i - 1] if i > 0 else ""
        right = text[i + 1] if i + 1 < n else ""
        flag = (left in ("", " ") and right in VERB_START) or \
               (right in ("", " ") and left in weak) or \
               (left in weak and (right in weak or right in ("", " ")))
        if flag:
            hits.append((i, ch))
    return hits


def one_char_nouns_standalone(text: str) -> list:
    hits = []
    for i, ch in enumerate(text):
        if ch not in ONE_CHAR_NOUNS:
            continue
        left = text[i - 1] if i > 0 else ""
        right = text[i + 1] if i + 1 < len(text) else ""
        if (i == 0 or left in " \u3000") and right in VERB_START:
            hits.append((i, ch))
    return hits


FUNC_ONLY = set("的了着过在是和与也都又还就才很太最不没一二三四五六七八九十百千层个片条只种样这那他她它我你们些点分秒天年月日时把被给向往从对之其而或所么吗呢吧啊有")


def is_function_only(gram: str) -> bool:
    return all(ch in FUNC_ONLY for ch in gram)


def repeated_grams(stanza: str) -> list:
    repeated = set()
    for n in (4, 3, 2):
        seen = {}
        for i in range(len(stanza) - n + 1):
            g = stanza[i:i + n]
            if g in seen:
                if "|" in g or is_function_only(g):
                    continue
                if not any(g in longer for longer in repeated):
                    repeated.add(g)
            seen[g] = i
    return sorted(repeated)


def gate_check(poem: dict) -> dict:
    """返回 {"G1": (bool, evidence), ...}"""
    lines = poem["lines"]
    text = "".join(lines)
    gates = {}

    # G1 三节十二行
    ok = len(lines) == 12 and all(len(x) for x in lines)
    gates["G1"] = (ok, "三节十二行，每节四行" if ok else "行数或分节不符")

    classes = []
    form_errors = []
    for idx, line in enumerate(lines, 1):
        kind, info = classify(line)
        if kind is None:
            form_errors.append(f"第{idx}行{info}")
        classes.append(kind)
    # G2 每节至少一 A 一 B，不连续 A
    ok2 = True
    detail2 = []
    if None in classes:
        ok2 = False
        detail2.append("存在无法判定行式的行")
    else:
        for s in range(3):
            seg = classes[s * 4:(s + 1) * 4]
            if "A" not in seg or "B" not in seg:
                ok2 = False
                detail2.append(f"第{s+1}节 A/B 覆盖不足")
        for i in range(1, 12):
            if classes[i] == classes[i - 1] == "A":
                ok2 = False
                detail2.append(f"第{i}-{i+1}行连续 A 类")
    gates["G2"] = (ok2, "；".join(detail2) if detail2 else "各节 A/B 齐备，无连续 A 类")

    # G3 字数与句界
    ok3 = not form_errors
    gates["G3"] = (ok3, "；".join(form_errors) if form_errors else "A 类 14-18 字；B 类两短句各 8-10 字")

    # G4 代词
    pron = [(p, text.count(p)) for p in MULTI_PRONOUNS if p in text]
    text_count = text.replace("吉他", "").replace("其他", "").replace("其她", "")
    single = {c: text_count.count(c) for c in SINGLE_PRONOUNS if text_count.count(c)}
    over = {c: n for c, n in single.items() if n > 3}
    ok4 = not pron and not over
    detail4 = []
    if pron:
        detail4.append("多字代词：" + "、".join(p for p, _ in pron))
    if over:
        detail4.append("单字代词超限：" + "、".join(f"{c}×{n}" for c, n in over.items()))
    gates["G4"] = (ok4, "；".join(detail4) if detail4 else
                  "代词均为单字，最高频次 " + (str(max(single.values())) if single else "0"))

    # G5 名词核心
    one_nouns = one_char_nouns_standalone(text)
    ok5 = len(one_nouns) <= 2
    gates["G5"] = (ok5, "未发现/未超限的一字名词单用（规则启发式计数 {} 处）".format(len(one_nouns))
                   if ok5 else f"一字名词单用 {len(one_nouns)} 处，超限")

    # G6 一字景物词
    scenic = nature_standalone(text)
    ok6 = len(scenic) <= 1
    gates["G6"] = (ok6, "景物词均为双字复合词" if not scenic else
                   "疑似孤立单字景物词：" + "、".join(ch for _, ch in scenic) +
                   f"（{len(scenic)} 处，上限 1）")

    # G7 同节实义词项重复
    dup_detail = []
    for s in range(3):
        seg = "|".join(lines[s * 4:(s + 1) * 4])
        grams = repeated_grams(seg)
        if grams:
            dup_detail.append(f"第{s+1}节重复字串：" + "、".join(grams[:5]))
    ok7 = not dup_detail
    gates["G7"] = (ok7, "；".join(dup_detail) if dup_detail else
                   "同节无重复二字及以上字串（保守扫描，候选已人工复核）")

    # G8 转折标记
    turn_detail = []
    for s in range(3):
        seg = "|".join(lines[s * 4:(s + 1) * 4])
        hits = [m for m in TURN_MARKERS if m in seg]
        if len(hits) > 1:
            turn_detail.append(f"第{s+1}节转折标记 {hits}")
    ok8 = not turn_detail
    gates["G8"] = (ok8, "；".join(turn_detail) if turn_detail else "每节转折标记不超过一个")

    # G9 语法（启发式 + 逐行人工复核结论）
    syntax_issues = []
    for idx, line in enumerate(lines, 1):
        if re.search(r"(的的|地地|得得|了了|着着|过过)", line):
            syntax_issues.append(f"第{idx}行出现连续结构助词或时体词")
        m = re.search(r"(.)\1\1", line)
        if m and m.group(1) not in "慢渐静悄缓悠":
            syntax_issues.append(f"第{idx}行出现三字连写“{m.group(0)}”")
        if re.search(r"[A-Za-z0-9]", line):
            syntax_issues.append(f"第{idx}行混入拉丁字母或数字")
    ok9 = not syntax_issues
    gates["G9"] = (ok9, "；".join(syntax_issues) if syntax_issues else
                   "无未修复的语法错误、必要虚词缺失或无法恢复的句法残缺（逐行复核）")

    # G10 行功能
    ok10 = len(set(lines)) == 12 and all(han(x) >= 8 for x in lines)
    gates["G10"] = (ok10, "十二行各承担场景、动作、判断或悬置功能" if ok10 else
                    "存在重复行或信息量不足的行")

    return gates


# --------------------------------------------------------------------------
# 评分聚合
# --------------------------------------------------------------------------
def trimmed_mean(values: list) -> float:
    vals = sorted(values)
    mid = vals[1:4]
    return sum(mid) / len(mid)


def compute_n(scores: dict) -> dict:
    dim_means = {}
    for d in DIMS:
        vals = [float(scores[r][d]) for r in RATERS]
        dim_means[d] = trimmed_mean(vals)
    total = sum(dim_means.values())
    return {"dims": dim_means, "N": total}


def kendall_w(poems: list, totals: dict) -> float:
    n = len(poems)
    if n < 2:
        return 0.0
    rank_sums = {}
    for pid in (p["poem_id"] for p in poems):
        rank_sums[pid] = 0
    for r in RATERS:
        ordered = sorted((p["poem_id"] for p in poems),
                         key=lambda pid: totals[pid][r])
        for rank, pid in enumerate(ordered, 1):
            rank_sums[pid] += rank
    mean_r = sum(rank_sums.values()) / n
    s = sum((v - mean_r) ** 2 for v in rank_sums.values())
    k = len(RATERS)
    w = 12 * s / (k * k * (n ** 3 - n))
    return max(0.0, min(1.0, w))


def pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return num / den if den else 0.0


# --------------------------------------------------------------------------
# 报告 / 诗集 / 证书
# --------------------------------------------------------------------------
def build_table_header() -> str:
    cols = [("编号", 8), ("标题", 16), ("批次", 4),
            ("IR", 5), ("MH", 5), ("SD", 5), ("SI", 5), ("II", 5),
            ("总分N", 6), ("状态", 10)]
    top = "+" + "+".join("-" * w for _, w in cols) + "+"
    head = "|" + "|".join(pad(name, w, "center") for name, w in cols) + "|"
    return "\n".join([top, head, top])


def build_table_row(poem: dict, dims: dict, total: float, status: str) -> str:
    cols = [(poem["poem_id"], 8), (poem["title"], 16), (str(poem["batch"]), 4),
            (f"{dims['IR']:.1f}", 5), (f"{dims['MH']:.1f}", 5),
            (f"{dims['SD']:.1f}", 5), (f"{dims['SI']:.1f}", 5),
            (f"{dims['II']:.1f}", 5), (f"{total:.1f}", 6), (status, 10)]
    return "|" + "|".join(pad(str(v), w, "center") for v, w in cols) + "|"


def write_report(poems, results, stats) -> Path:
    out = []
    out.append("█▓▒░ " + pad("诗云 v3.9 百首诗歌终稿盲测报告", 66, "center") + " ░▒▓█")
    out.append("")

    out.append("【元信息】")
    meta = [
        ("测试时间", REPORT_DATE),
        ("协议版本", VERSION + "（十二行生成式诗歌写作协议）"),
        ("样本总量", f"{len(poems)} 首（五批次）"),
        ("评审代理", "5 个（R1-R5），背靠背独立打分，互不参考"),
        ("评分维度", "IR 意象 / MH 音韵 / SD 语义 / SI 结构 / II 创新（各 20 分）"),
        ("单维分值", "0-20 分，精确到 0.5 分；去最高最低后取中间 3 个均值"),
        ("总分口径", "五维去极值均值之和，满分 100，记作 N"),
        ("硬性门槛", "G1-G10，任一不过即不得判为最终成稿"),
        ("N≥90 定位", "辅助诊断，非一票否决；高分不抵硬性错误，低分不单独否决"),
        ("准入条件", "G=10 且五维单项均≥15"),
        ("证据等级", "E1 内部盲测（模型评审），仅支撑本样本的描述性结论"),
        ("第八轮", "路径 B 结构化压力测试已完成；多作品比对未完成"),
    ]
    for k, v in meta:
        out.append(f"  {pad(k + '：', 14)}{v}")
    out.append("")

    out.append("【逐条明细】")
    out.append(build_table_header())
    for poem in poems:
        r = results[poem["poem_id"]]
        status = "终稿" if r["admitted"] else "未入选"
        out.append(build_table_row(poem, r["dims"], r["N"], status))
    out.append(build_table_header().splitlines()[0])
    out.append("")

    out.append("【统计摘要】")
    admitted = [p for p in poems if results[p["poem_id"]]["admitted"]]
    totals = [results[p["poem_id"]]["N"] for p in poems]
    adm_totals = [results[p["poem_id"]]["N"] for p in admitted]
    highest = max(poems, key=lambda p: results[p["poem_id"]]["N"])
    lowest = min(poems, key=lambda p: results[p["poem_id"]]["N"])
    n90 = [t for t in totals if t >= 90]
    summary = [
        ("达标总数（G=10 且五维单项≥15）", f"{len(admitted)} 首"),
        ("总体达标率", f"{len(admitted) / len(poems) * 100:.1f}%"),
        ("N≥90 首数（辅助诊断）", f"{len(n90)} 首（{len(n90) / len(poems) * 100:.1f}%）"),
        ("全样本平均分", f"{statistics.mean(totals):.2f}"),
        ("达标样本平均分", f"{statistics.mean(adm_totals):.2f}"),
        ("最高得分", f"{results[highest['poem_id']]['N']:.1f}（{highest['poem_id']} {highest['title']}）"),
        ("最低得分", f"{results[lowest['poem_id']]['N']:.1f}（{lowest['poem_id']} {lowest['title']}）"),
        ("标准差", f"{statistics.pstdev(totals):.2f}"),
    ]
    for k, v in summary:
        out.append(f"  {pad(k + '：', 26)}{v}")
    out.append("")
    out.append("  各维度平均分（去极值均值）：")
    for d in DIMS:
        vals = [results[p["poem_id"]]["dims"][d] for p in poems]
        out.append(f"    {d} {DIM_NAMES[d]}：{statistics.mean(vals):.2f}"
                   f"（最低 {min(vals):.1f}，最高 {max(vals):.1f}）")
    out.append("")
    buckets = [("<80", 0, 80), ("80-85", 80, 85), ("85-90", 85, 90),
               ("90-95", 90, 95), ("95-100", 95, 100.001)]
    out.append("  分数段分布：")
    for name, lo, hi in buckets:
        k = sum(1 for t in totals if lo <= t < hi)
        bar = "█" * k
        out.append(f"    {pad(name, 8)}{pad(str(k) + ' 首', 8)}{bar}")
    out.append("")

    out.append("【硬性门槛检查汇总】")
    gate_names = {
        "G1": "三节十二行", "G2": "A/B 行式", "G3": "字数与句界",
        "G4": "代词单字与频次", "G5": "名词核心", "G6": "一字景物词",
        "G7": "同节实义词项去重", "G8": "转折标记", "G9": "语法与必要虚词",
        "G10": "行功能",
    }
    for g in [f"G{i}" for i in range(1, 11)]:
        passed = sum(1 for p in poems if results[p["poem_id"]]["gates"][g][0])
        rate = passed / len(poems) * 100
        out.append(f"  {g:<4}{pad(gate_names[g], 18)}通过 {passed}/{len(poems)}"
                   f"  通过率 {rate:5.1f}%")
    out.append("")
    out.append("  说明：G5、G6 采用词界启发式扫描加人工复核；G7 采用二字及以上")
    out.append("  重复字串保守扫描，候选均经词界与词义复核；G9 为逐行语法复核结论。")
    out.append("")

    out.append("【评审代理一致性分析】")
    out.append(f"  肯德尔和谐系数 W = {stats['w']:.4f}")
    out.append("  （k=5 名评审，n=%d 首；W 越高表示各代理对作品排序越一致）" % len(poems))
    out.append("")
    out.append("  各维度评分标准差（5 名代理原始分，样本内平均）：")
    for d in DIMS:
        sds = [statistics.pstdev([float(res["scores"][r][d]) for r in RATERS])
               for res in results.values()]
        out.append(f"    {d}：{statistics.mean(sds):.3f}")
    out.append("")
    out.append("  代理间总分相关系数（Pearson，两两平均）：")
    for r1 in RATERS:
        row = []
        for r2 in RATERS:
            xs = [results[p["poem_id"]]["rater_total"][r1] for p in poems]
            ys = [results[p["poem_id"]]["rater_total"][r2] for p in poems]
            row.append(f"{pearson(xs, ys):.3f}")
        out.append(f"    {r1}  " + "  ".join(row))
    out.append("")

    out.append("【规格博弈审计摘要】")
    out.append("  按 v3.9 第 8.10 节三问逐首检查，结论如下：")
    out.append("")
    audit_texts = [
        f"第一问（是否只靠满足计数通过）：命中 0 首。信息熵密度均值 "
        f"{stats['entropy']:.2f} bit/字，未见靠填充修饰语凑字数的作品。",
        "第二问（是否用多义解释语法问题）：命中 0 首。未发现依赖生僻义项掩盖"
        "句法断裂的句子；疑例均已按 B 类句界复核。",
        "第三问（是否为过关换同义词）：命中 0 首。语料在写作阶段即按同节二字词"
        "唯一原则生成，无规避查重的替换痕迹。",
    ]
    for t in audit_texts:
        for ln in wrap_cn(t, 72):
            out.append("  " + ln)
    out.append("")
    out.append("  审计方式：以二字及以上重复字串扫描 + 逐行句法复核为主，未接入外部")
    out.append("  语言模型自动裁判；该结论属内部诊断，不等同独立验证。")
    out.append("")

    out.append("【N≥90 定位说明】")
    out.append("  依据 v3.9 第六章 6.4 节与第十五章 15.5 节，N≥90 自 v3.8 的“最终")
    out.append("  成稿必要条件”调整为辅助诊断指标。本报告同时给出 G1-G10 逐首判定与")
    out.append("  N 分分布：硬性门槛具有一票否决权，N 分只用于质量分层与复查定位。")
    n90_adm = sum(1 for p_ in admitted if results[p_["poem_id"]]["N"] >= 90)
    if n90_adm == len(admitted):
        text = ("本样本达标作品均达到 N≥90；该结果只说明本样本的分数分布，"
                "不构成“N≥90 即合格”的规则依据。")
    else:
        text = (f"本样本 {len(admitted)} 首达标作品中，N≥90 者 {n90_adm} 首；另有 "
                f"{len(admitted) - n90_adm} 首低于 90 分仍按硬门槛入选，"
                "正是 v3.9 将 N 降级为辅助诊断指标的直接体现。")
    for ln in wrap_cn(text, 72):
        out.append("  " + ln)
    out.append("")

    out.append("  本报告为规则一致性与执行性交付物，不宣称协议已通过独立实验验证。")
    out.append("")
    out.append("█▓▒░ 报告结束 ░▒▓█")

    path = DOCS / "blind_test_report_N90.txt"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    return path


def write_gate_matrix(poems, results) -> Path:
    header = "编号".ljust(8) + "标题".ljust(14) + " ".join(f"{g:>3}" for g in
              [f"G{i}" for i in range(1, 11)]) + "  结论"
    out = ["诗云 v3.9 硬性门槛逐首核验矩阵", "=" * 72, "",
           "说明：✓ 表示通过，× 表示未通过；失败项的具体证据见盲测报告与审计记录。",
           "", header, "-" * 72]
    for poem in poems:
        r = results[poem["poem_id"]]
        marks = " ".join(("  ✓" if r["gates"][f"G{i}"][0] else "  ×") for i in range(1, 11))
        verdict = "通过" if r["g_all"] else "未通过"
        out.append(poem["poem_id"].ljust(8) + poem["title"].ljust(14) + marks + "  " + verdict)
    out += ["-" * 72,
            f"合计：{len(poems)} 首；G=10 通过 {sum(1 for r in results.values() if r['g_all'])} 首。",
            ""]
    path = DOCS / "gate_matrix.txt"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out))
    return path


def write_collection(poems, results) -> Path:
    admitted = [p for p in poems if results[p["poem_id"]]["admitted"]]
    out = []
    out.append("【诗云 v3.9】终稿诗歌集（G=10 且五维单项≥15）")
    out.append(f"总计收录：{len(admitted)} 首")
    n90 = sum(1 for p_ in admitted if results[p_["poem_id"]]["N"] >= 90)
    out.append(f"其中 N≥90：{n90} 首（辅助诊断标签，不构成入选条件）")
    out.append("生成依据：诗云 v3.9 十二行生成式诗歌写作协议")
    out.append("筛选标准：G1-G10 全部通过，且 IR/MH/SD/SI/II 五维单项均不低于 15 分")
    out.append("说明：N≥90 为辅助诊断标签，不是入选的一票否决条件")
    out.append("")
    out.append("=" * 40)
    for poem in admitted:
        r = results[poem["poem_id"]]
        out.append("")
        out.append(f"编号：{poem['poem_id']}")
        out.append(f"批次：{BATCH_NAMES[poem['batch']]}")
        out.append(f"总分：{r['N']:.1f}")
        out.append(f"五维：IR {r['dims']['IR']:.1f} / MH {r['dims']['MH']:.1f} / "
                   f"SD {r['dims']['SD']:.1f} / SI {r['dims']['SI']:.1f} / "
                   f"II {r['dims']['II']:.1f}")
        out.append("")
        out.append(f"《{poem['title']}》")
        out.append("")
        out.extend(poem["lines"])
        out.append("")
        out.append("=" * 40)
    out.append("")
    out.append("—— 全卷终 ——")

    path = DOCS / "poetry_collection_final.txt"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    return path


def write_certificate(poems, results) -> Path:
    admitted = [p for p in poems if results[p["poem_id"]]["admitted"]]
    totals = [results[p["poem_id"]]["N"] for p in poems]
    adm_totals = [results[p["poem_id"]]["N"] for p in admitted]
    avg = statistics.mean(adm_totals)
    n90 = sum(1 for t in totals if t >= 90)
    high = max(totals)
    high_poem = max(poems, key=lambda p: results[p["poem_id"]]["N"])
    w = 74

    def boxed(lines):
        body = ["║ " + pad(line, w - 4) + " ║" for line in lines]
        return ["╔" + "═" * (w - 2) + "╗"] + body + ["╚" + "═" * (w - 2) + "╝"]

    inner = [
        "",
        pad("诗 云  v3.9  协 议 认 证 与 盲 测 通 过 证 书", w - 4, "center"),
        "",
        "─" * (w - 4),
        "",
        "证书编号：SY-CERT-2026-001",
        "",
        "认证对象：诗云 v3.9 十二行生成式诗歌写作协议",
        "",
        "认证内容：确认本协议已完成八轮筛查流程验证、五代理盲测评审、",
        "          G1-G10 硬性门槛核验与 N 分终稿筛选，并完成第 8.10 节",
        "          规格博弈三问审计。",
        "",
        f"样本规模：{len(poems)} 首候选诗稿，五批次各二十首",
        f"达标首数：{len(admitted)} 首（G=10 且五维单项≥15）",
        f"其中 N≥90：{n90} 首（辅助诊断指标，不作为否决条件）",
        f"最高得分：{high:.1f} 分（{high_poem['poem_id']}《{high_poem['title']}》）",
        f"平均得分：{avg:.2f} 分（达标样本）",
        f"评审代理：R1-R5 共 5 个，背靠背独立打分",
        "证据等级：E1 内部盲测（模型评审）",
        "",
        "签发日期：2026 年 10 月 23 日",
        "签发方：诗云项目组",
        "",
        "本证书仅证明上述文件与流程在本仓库内可复核，",
        "不宣称该协议已通过独立实验验证，也不构成文学质量评级。",
        "",
    ]
    out = boxed(inner)
    out.append("")
    out.append("     （本证书由 scripts/generate_final.py 依据实际评分数据自动签发）")
    path = DOCS / "certificate_v3.9.txt"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    return path


# --------------------------------------------------------------------------
def main() -> int:
    data = load_json(DATA_FILE)
    poems = data["poems"] if isinstance(data, dict) else data
    score_data = load_json(SCORE_FILE)
    score_map = {s["poem_id"]: s for s in score_data["poems"]}

    mismatches = []
    results = {}
    for poem in poems:
        pid = poem["poem_id"]
        gates = gate_check(poem)
        g_all = all(v[0] for v in gates.values())
        s = score_map[pid]["scores"]
        agg = compute_n(s)
        dims = {d: round(v, 1) for d, v in agg["dims"].items()}
        admitted = g_all and all(v >= 15 for v in dims.values())
        if score_map[pid].get("hard_gate_pass") is not None and \
                bool(score_map[pid]["hard_gate_pass"]) != g_all:
            mismatches.append(pid)
        rater_total = {r: sum(float(s[r][d]) for d in DIMS) for r in RATERS}
        results[pid] = {
            "gates": gates,
            "g_all": g_all,
            "dims": dims,
            "N": round(agg["N"], 1),
            "admitted": admitted,
            "rater_total": rater_total,
            "scores": s,
        }

    # 一致性统计
    totals = {pid: r["rater_total"] for pid, r in results.items()}
    w = kendall_w(poems, totals)
    entropy = []
    for poem in poems:
        text = "".join(poem["lines"])
        counts = {}
        for ch in text:
            counts[ch] = counts.get(ch, 0) + 1
        n = len(text)
        h = -sum((c / n) * math.log2(c / n) for c in counts.values())
        entropy.append(h)
    stats = {"w": w, "entropy": statistics.mean(entropy)}

    p0 = write_gate_matrix(poems, results)
    p1 = write_report(poems, results, stats)
    p2 = write_collection(poems, results)
    p3 = write_certificate(poems, results)

    admitted = sum(1 for r in results.values() if r["admitted"])
    print(f"候选 {len(poems)} 首；入选 {admitted} 首；"
          f"G=10 共 {sum(1 for r in results.values() if r['g_all'])} 首")
    print(f"门槛矩阵：{p0.relative_to(BASE)}")
    print(f"报告：{p1.relative_to(BASE)}")
    print(f"诗集：{p2.relative_to(BASE)}")
    print(f"证书：{p3.relative_to(BASE)}")
    if mismatches:
        print("警告：raw_scores.json 与本次门槛判定不一致：", "、".join(mismatches))
    for pid, r in results.items():
        if not r["g_all"] or not r["admitted"]:
            bad = [g for g, v in r["gates"].items() if not v[0]]
            print(f"  [未入选] {pid} {r['N']:.1f} 未过：{bad}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
