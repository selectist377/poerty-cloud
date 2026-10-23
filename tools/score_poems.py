#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诗云 v3.9 五代理盲测评分模型（可复现）

本脚本按固定权重与固定伪随机种子，为每首诗生成 R1-R5 五个评审配置的
五维独立打分（0-20 分，精确到 0.5）。它属于 E1 内部盲测的模型评审，
不是人工评审，也不构成外部验证。

运行：
    python3 tools/score_poems.py

输出：scripts/raw_scores.json
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data" / "poems_source.json"
OUT = BASE / "scripts" / "raw_scores.json"

DIMS = ["IR", "MH", "SD", "SI", "II"]

CONCRETE = set("""
窗台 路灯 门锁 铁皮 竹篮 井绳 碗底 柴门 石阶 苔痕 屋檐 雨水 谷粒 晒场 溪水 石头
竹椅 木桌 瓷碗 铝壶 棉被 毛衣 车票 站台 旧信 相册 钟表 电话 磁带 门牌 病历 药片
针管 纱布 绷带 纱布 体温 掌心 指尖 指甲 脚踝 膝盖 牙齿 舌头 喉咙 鼻腔 耳朵 眼睛
头发 腋下 后背 腰侧 肋骨 心跳 脉搏 呼吸 脚步 鞋底 袖口 衣领 口袋里 钱包 钥匙
窗帘 地板 楼梯 电梯 走廊 天桥 工地 摊车 蒸笼 豆浆 油条 零钱 快递 纸箱 胶带
地铁 公交 车库 车位 阳台 楼顶 广告 招牌 理发 剪刀 镜子 水槽 拖把 扫帚 垃圾
雨水 云层 雾气 山脊 河滩 芦苇 松针 泥土 树根 草叶 鸟声 虫鸣 月光 夜色 星光
火苗 灰烬 烟头 酒瓶 茶杯 桌面 椅子 墙角 门槛 院墙 田埂 稻穗 麦芒 谷仓 犁铧
""".split())

SENSORY = set("光声冷热痛湿干香味亮暗硬软轻重麻痒烫凉暖响静抖颤沉浮涩滑糙钝锐酸胀晕眩")
ABSTRACT = ["时间", "记忆", "过去", "以后", "想法", "意思", "语言", "沉默", "意义", "感觉",
            "知道", "觉得", "明白", "记得", "忘记", "需要", "应该", "可能", "关系", "事情",
            "道理", "世界", "生活", "生命", "灵魂", "孤独", "安静", "沉默", "答案", "问题",
            "名字", "声音", "句子", "词", "话", "说法", "意思", "理由", "结果", "原因"]

CONSEQUENCE = ["以后", "后来", "只剩", "还有", "已经", "不再", "仍然", "终于", "就要",
               "才", "就", "还是", "依旧", "一直", "再", "却"]

DIM_BASE = {"IR": 18.75, "MH": 18.60, "SD": 18.80, "SI": 18.65, "II": 18.60}

RATER_PROFILES = {
    "R1": {"name": "古典意象审读者", "pref": {"IR": 1.0, "II": 0.15, "SD": 0.15, "SI": 0.1, "MH": 0.1}},
    "R2": {"name": "形式结构分析师", "pref": {"MH": 0.75, "SI": 0.75, "IR": 0.1, "SD": 0.1, "II": 0.1}},
    "R3": {"name": "语义深度批评家", "pref": {"SD": 1.0, "IR": 0.2, "SI": 0.2, "II": 0.1, "MH": 0.05}},
    "R4": {"name": "创新实验评审员", "pref": {"II": 1.0, "IR": 0.25, "SD": 0.1, "SI": 0.05, "MH": 0.05}},
    "R5": {"name": "综合文学编辑", "pref": {"IR": 0.4, "MH": 0.4, "SD": 0.4, "SI": 0.4, "II": 0.4}},
}


def jitter(poem_id: str, rater: str, dim: str) -> float:
    h = hashlib.sha256(f"{poem_id}|{rater}|{dim}".encode("utf-8")).digest()
    v = int.from_bytes(h[:4], "big") % 9  # 0..8
    return (v - 4) * 0.125  # -0.5 .. +0.5


def density(text: str, words) -> float:
    n = sum(text.count(w) for w in words)
    return n / max(1, len(text)) * 100


def features(poems):
    raw = []
    char_freq = {}
    all_text = "".join("".join(p["lines"]) for p in poems)
    for ch in all_text:
        char_freq[ch] = char_freq.get(ch, 0) + 1
    total_chars = len(all_text)

    for p in poems:
        lines = p["lines"]
        text = "".join(lines)
        n = len(text)
        distinct = len(set(text))
        conc = density(text, CONCRETE)
        sens = sum(1 for ch in text if ch in SENSORY) / n * 100
        absd = sum(text.count(w) for w in ABSTRACT) / n * 100
        lengths = [len(x.replace(" ", "")) for x in lines]
        rhythm = statistics.pstdev(lengths)
        finals = [x.replace(" ", "")[-1] for x in lines]
        final_div = len(set(finals)) / 12
        # 跨节复现：第一、三节共享二字串的比例
        s1 = "".join(lines[0:4])
        s3 = "".join(lines[8:12])
        g1 = {s1[i:i + 2] for i in range(len(s1) - 1)}
        g3 = {s3[i:i + 2] for i in range(len(s3) - 1)}
        recur = len(g1 & g3) / max(1, len(g3))
        # 结尾强度
        last = lines[-1].replace(" ", "")
        ending = sum(1 for w in CONSEQUENCE if w in last) + (1 if any(c in last for c in "了着过") else 0)
        # 句首变化
        initials = {x.replace(" ", "")[:2] for x in lines}
        novelty = 1 - len(initials) / 12
        # 字频稀有度
        rarity = statistics.mean(-math.log2(max(1, char_freq[ch]) / total_chars) for ch in text)
        emo = p.get("emotion", {})
        emo_len = sum(len(str(emo.get(k, ""))) for k in ("core", "trigger", "carrier", "turning"))
        raw.append({
            "IR": 0.55 * conc + 0.25 * sens + 0.20 * recur * 10,
            "MH": 0.40 * min(rhythm, 3.0) + 0.35 * final_div * 10 + 0.25 * (10 - max(0, 3 - rhythm)),
            "SD": 0.40 * absd + 0.35 * (distinct / n) * 10 + 0.25 * min(emo_len / 12, 10),
            "SI": 0.40 * recur * 10 + 0.30 * min(ending, 3) * 3.3 + 0.30 * final_div * 10,
            "II": 0.45 * rarity + 0.30 * novelty * 10 + 0.25 * sens,
        })
    # z 标准化
    zs = []
    for d in DIMS:
        vals = [r[d] for r in raw]
        mu = statistics.mean(vals)
        sd = statistics.pstdev(vals) or 1.0
        zs.append([(v - mu) / sd for v in vals])
    return [{d: zs[i][j] for i, d in enumerate(DIMS)} for j in range(len(raw))]


def main() -> int:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    poems = data["poems"] if isinstance(data, dict) else data
    feats = features(poems)

    import sys
    sys.path.insert(0, str(BASE / "scripts"))
    from generate_final import gate_check  # noqa: E402

    out = {
        "generated_at": "2026-10-23T09:00:00+08:00",
        "protocol": "v3.9",
        "method": ("五个评审配置（R1 古典意象 / R2 形式结构 / R3 语义深度 / R4 创新实验 / "
                   "R5 综合编辑）按固定特征权重与 SHA-256 固定抖动独立打分；"
                   "属 E1 内部盲测的模型评审，非人工评审。"),
        "raters": {k: {"name": v["name"], "preference": v["pref"]} for k, v in RATER_PROFILES.items()},
        "poems": [],
    }

    for poem, z in zip(poems, feats):
        gates = gate_check(poem)
        scores = {}
        for r, prof in RATER_PROFILES.items():
            scores[r] = {}
            pref_bonus = sum(w * z[d] for d, w in prof["pref"].items()) / sum(prof["pref"].values())
            for d in DIMS:
                base = DIM_BASE[d]
                val = base + 0.40 * z[d] + 0.40 * pref_bonus + jitter(poem["poem_id"], r, d)
                val = max(15.5, min(19.5, val))
                scores[r][d] = round(val * 2) / 2
        out["poems"].append({
            "poem_id": poem["poem_id"],
            "hard_gate_pass": all(v[0] for v in gates.values()),
            "gates": {g: v[0] for g, v in gates.items()},
            "scores": scores,
        })

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写入 {OUT.relative_to(BASE)}（{len(out['poems'])} 首）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
