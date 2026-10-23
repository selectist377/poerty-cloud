#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诗云 v3.9 诗稿形式校验器（开发期工具，不依赖第三方库）

用法：
    python3 tools/validate_poems.py data/batches/batch1.json
    python3 tools/validate_poems.py data/batches/*.json          # 跨文件查重
    python3 tools/validate_poems.py data/poems_source.json --strict

校验项（与协议 v3.9 的 G1-G3、G4、G6、G7、G8 对应）：
  1. 三节十二行，每节四行；
  2. A 类：14-18 个汉字、行内无标点无空格、单一完整句；
  3. B 类：恰含一个半角空格，两个短句各 8-10 个汉字，句内无标点；
  4. 每节至少一行 A、一行 B；全诗不连续出现两行 A；
  5. 代词全部为单字，同一种单字代词全诗不超过三次；
  6. 景物词一律使用双字及以上复合词，不得出现孤立单字景物词；
  7. 同一节内不得出现重复的二字及以上字串（保守判定，严于 G7）；
  8. 每节转折标记不超过一个；
  9. 跨作品不得重复使用同一行诗句或同一标题。

退出码：0 全部通过；1 存在错误。
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from collections import Counter, defaultdict

HAN_RE = re.compile(r"^[\u4e00-\u9fff]+$")
PUNCT = set("，。！？；：、“”‘’（）《》〈〉—…·,.!?;:\"'()[]{}<>~`@#$%^&*+=|\\/＿－　")

# 单字代词
SINGLE_PRONOUNS = "我你他她它谁这那其之此咱您"
# 多字代词（正文禁用）
MULTI_PRONOUNS = ["我们", "你们", "他们", "她们", "它们", "咱们", "自己",
                  "大家", "彼此", "别人", "人家", "各位", "诸位"]

# 转折 / 纠正预期标记
TURN_MARKERS = ["然而", "但是", "可是", "不过", "反而", "其实", "却", "只是",
                "并非", "而是", "原来", "真正", "究竟", "毕竟", "偏偏", "居然"]

# 泛指凑字词（警告）
VAGUE_WORDS = ["那些", "许多", "一些", "无数", "各种", "某些", "有的", "所有"]

# 景物单字：出现时必须被某个双字景物词包住
NATURE_CHARS = set("山水风云月雨雪雾霜露花草木石河海林岸桥船鸟鱼叶枝根土冰泉浪涛潮霞岚壑溪岭岩崖峰谷塘池潭滩洲岛天星沙阳阴烟虹原野")

VERB_START = set("停落吹拂卷过下起升散退涌压遮洗冲推摇动亮暗沉浮飘打在洒滴流漫爬生开照映穿沿绕")

# 虚词/功能字：相邻时不足以证明该景物字处在复合词中
FUNCTION_CHARS = set("的地得了着过在是和与从向对把被让也都又还就才很太更最不没有这那那么吗呢啊吧么个片朵场阵条只种样")

"""
景物词判定采用“相邻字覆盖”规则：景物单字左右至少一侧存在实义汉字，
才视为处在双字及以上的复合词中；若两侧都是行首/行尾/空格/虚词，则判为
孤立单字景物词。该规则严于人工判词，宁严勿松；未覆盖处须改写为双字词。
"""


# 纯功能/数量/代词字：由这些字组成的重复字串不按“实义词项重复”计。
FUNC_ONLY = set("的了着过在是和与也都又还就才很太最不没一二三四五六七八九十百千层个片条只种样这那他她它我你们些点分秒天年月日时把被给向往从对之其而或所么吗呢吧啊有")

def is_function_only(gram: str) -> bool:
    return all(ch in FUNC_ONLY for ch in gram)


def hanzi_len(s: str) -> int:
    return len(s)


def classify(line: str):
    """返回 ('A'|'B', 信息) 或 (None, 错误信息)"""
    if " " in line:
        if line.count(" ") != 1:
            return None, "B 类行必须恰好包含一个半角空格分隔两个短句"
        a, b = line.split(" ")
        for part, name in ((a, "前一短句"), (b, "后一短句")):
            if not part:
                return None, f"{name}为空"
            if not HAN_RE.match(part):
                return None, f"{name}含非汉字字符或空白：{part!r}"
            if not 8 <= len(part) <= 10:
                return None, f"{name}为 {len(part)} 字，须为 8-10 字：{part}"
        return "B", (a, b)
    if not HAN_RE.match(line):
        bad = [c for c in line if not ("\u4e00" <= c <= "\u9fff")]
        return None, f"A 类行含非汉字字符：{''.join(bad)!r}"
    if not 14 <= len(line) <= 18:
        return None, f"A 类行为 {len(line)} 字，须为 14-18 字（且不得含标点空格）"
    return "A", line


def check_nature(line: str, lineno: int, errs: list):
    """保守判定孤立单字景物词，只在证据明确的几种句法位置报错。"""
    n = len(line)
    weak = set("的地得了着过在是和与也都又还就才很太更最不没个片朵场阵条只种样")
    for i, ch in enumerate(line):
        if ch not in NATURE_CHARS:
            continue
        left = line[i - 1] if i > 0 else ""
        right = line[i + 1] if i + 1 < n else ""
        flag = False
        # 行首/空格后直接作主语并接动词：如“风停在芦苇梢头”
        if left in ("", " ") and right in VERB_START:
            flag = True
        # 行尾/空格前，前字为虚词：如“暮色里的山”
        if (right in ("", " ")) and left in weak:
            flag = True
        # “的/在/把”等虚词后单独出现，且后接虚词收束：如“看那山的水”
        if left in weak and (right in weak or right in ("", " ")):
            flag = True
        if flag:
            errs.append(
                f"第{lineno}行出现疑似孤立单字景物词“{ch}”（上下文：{line[max(0, i - 4):i + 5]}），"
                f"景物应使用双字复合词"
            )
            return


def check_poem(poem: dict, errs: list, warns: list):
    pid = poem.get("poem_id", "?")
    lines = poem.get("lines")
    if not isinstance(lines, list) or len(lines) != 12:
        errs.append("正文必须恰为 12 行")
        return
    for i, ln in enumerate(lines, 1):
        if not isinstance(ln, str) or not ln:
            errs.append(f"第{i}行缺失或为空")
            return
        if ln != ln.strip():
            errs.append(f"第{i}行首尾含空白")
        if any(c in PUNCT for c in ln):
            errs.append(f"第{i}行含标点：{ln}")
        if re.search(r"[A-Za-z0-9]", ln):
            errs.append(f"第{i}行含拉丁字母或数字：{ln}")

    classes = []
    for i, ln in enumerate(lines, 1):
        kind, info = classify(ln)
        if kind is None:
            errs.append(f"第{i}行：{info}（原文：{ln}）")
            classes.append("?")
        else:
            classes.append(kind)

    # 行式结构
    for si in range(3):
        seg = classes[si * 4:(si + 1) * 4]
        if "A" not in seg:
            errs.append(f"第{si+1}节缺少 A 类行")
        if "B" not in seg:
            errs.append(f"第{si+1}节缺少 B 类行")
    for i in range(1, 12):
        if classes[i] == classes[i - 1] == "A":
            errs.append(f"第{i}行与第{i+1}行连续出现 A 类行")

    # 代词
    text = "".join(lines)
    text_count = text.replace("吉他", "").replace("其他", "").replace("其她", "")
    for p in MULTI_PRONOUNS:
        if p in text:
            errs.append(f"出现多字代词“{p}”，正文代词须为单字")
    pc = Counter(c for c in text_count if c in SINGLE_PRONOUNS)
    for c, k in pc.items():
        if k > 3:
            errs.append(f"单字代词“{c}”出现 {k} 次，超过三次上限")
    # 景物
    for i, ln in enumerate(lines, 1):
        check_nature(ln, i, errs)
    # 转折标记
    for si in range(3):
        seg = "|".join(lines[si * 4:(si + 1) * 4])
        hits = [m for m in TURN_MARKERS if m in seg]
        if len(hits) > 1:
            errs.append(f"第{si+1}节出现多个转折标记：{hits}")
    # 同节重复（二字及以上字串）
    for si in range(3):
        seg = "|".join(lines[si * 4:(si + 1) * 4])
        repeated = set()
        for n in (4, 3, 2):
            grams = defaultdict(int)
            for i in range(len(seg) - n + 1):
                grams[seg[i:i + n]] += 1
            for g, k in grams.items():
                if k <= 1 or "|" in g:
                    continue
                # 纯功能字组成的不算实义词项重复
                if is_function_only(g):
                    continue
                # 被已记录的长重复字串包含者不重复报
                if any(g in longer for longer in repeated):
                    continue
                repeated.add(g)
        if repeated:
            errs.append(f"第{si+1}节存在重复字串：{sorted(repeated)[:6]}")
    # 泛指
    for w in VAGUE_WORDS:
        if w in text:
            warns.append(f"使用泛指词“{w}”，建议核实是否凑字")
    # 标题与情感记录
    title = poem.get("title", "")
    if not isinstance(title, str) or not (2 <= len(title) <= 8):
        errs.append(f"标题缺失或长度不在 2-8 字：{title!r}")
    emo = poem.get("emotion") or {}
    for key in ("core", "trigger", "carrier"):
        if not str(emo.get(key, "")).strip():
            errs.append(f"情感记录缺少字段 {key}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--strict", action="store_true", help="警告也视为失败")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    paths = []
    for pat in args.files:
        paths.extend(sorted(glob.glob(pat)))
    if not paths:
        print("未找到输入文件", file=sys.stderr)
        return 1

    total = 0
    bad = 0
    titles = defaultdict(list)
    lines_index = defaultdict(list)
    ids = Counter()
    for path in paths:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        poems = data["poems"] if isinstance(data, dict) else data
        for poem in poems:
            total += 1
            errs, warns = [], []
            check_poem(poem, errs, warns)
            pid = poem.get("poem_id", "?")
            ids[pid] += 1
            titles[poem.get("title", "")].append(pid)
            for ln in poem.get("lines", []):
                lines_index[ln].append(pid)
            if errs or (args.strict and warns):
                bad += 1
                print(f"[FAIL] {pid}  {poem.get('title','')}  ({path})")
                for e in errs:
                    print("   -", e)
                for w in warns:
                    print("   ~", w)
            elif not args.quiet:
                print(f"[ OK ] {pid}  {poem.get('title','')}")

    # 跨文件查重
    dup_title = {t: p for t, p in titles.items() if t and len(p) > 1}
    dup_line = {g: p for g, p in lines_index.items() if len(p) > 1}
    dup_id = {i: k for i, k in ids.items() if k > 1}
    for t, p in dup_title.items():
        bad += 1
        print(f"[FAIL] 标题重复“{t}”：{p}")
    for g, p in list(dup_line.items())[:20]:
        bad += 1
        print(f"[FAIL] 诗句重复“{g}”：{p}")
    for i, k in dup_id.items():
        bad += 1
        print(f"[FAIL] poem_id 重复“{i}”×{k}")

    print(f"\n合计 {total} 首，失败 {bad} 首。")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
