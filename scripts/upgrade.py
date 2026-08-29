#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
upgrade.py — 增量升级（v3：旧 merged.json → v3 增量层，不重跑全量蒸馏）

用法：
  python3 upgrade.py <merged.json> [--stats <stats.json>]
      [--out <out.json>] [--offline] [--prompts <prompts目录>]

原理（v3 增量升级机制）：
  - 旧产物（v1/v2，无 template_version 或 <3）本体格式稳定、继续可读；
    v3 只加"增量层"：persona.eras（时段化人格）/ persona.core（核心稳定特质）/
    persona.evolution（演变轨迹）/ user_profile（用户侧画像）/ template_version=3
  - 输入 = 旧 merged.json 摘要 + 统计摘要 → 1 次 merge 级 LLM 调用补生成新字段
    （≈全量重跑的 5%），**不重新逐段蒸馏**；corpus/stats/segments 原样保留
  - 已升级（template_version>=3）→ 直接跳过，不重复计费
  - --offline：无 key 的启发式升级（eras 从 timeline 推导），仅用于验证管线

环境变量（同 distill.py）：
  LLM_API_BASE / LLM_API_KEY / LLM_MODEL —— 密钥只从环境变量读取
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from distill import (api_config, call_json, with_retry,  # noqa: E402
                     stats_summary, per_era_stats)

TEMPLATE_VERSION = 3

UPGRADE_FIELDS = ("persona.eras", "persona.core", "persona.evolution",
                  "user_profile")


def detect_template_version(merged):
    """旧产物无 template_version 视为 v1；v3 及以上视为已升级。"""
    return int(merged.get("template_version") or 1)


def build_old_summary(merged):
    """旧产物 → 摘要文本（升级模板输入；只摘旧字段，不编造）。"""
    p = merged.get("persona") or {}
    m = merged.get("memories") or {}
    L = []
    L.append("summary: %s" % (merged.get("summary") or "（无）"))
    traits = p.get("core_traits") or []
    if traits:
        L.append("core_traits: %s" % json.dumps(
            [t.get("trait") if isinstance(t, dict) else t for t in traits],
            ensure_ascii=False))
    expr = p.get("expression") or {}
    cps = expr.get("catchphrases") or []
    if cps:
        L.append("catchphrases: %s" % json.dumps(
            [c.get("phrase") for c in cps][:10], ensure_ascii=False))
    rel = p.get("relationship") or {}
    sc = rel.get("stage_changes") or []
    if sc:
        L.append("stage_changes: %s" % json.dumps(sc, ensure_ascii=False)[:800])
    tl = m.get("timeline") or []
    if tl:
        L.append("timeline: %s" % json.dumps(tl, ensure_ascii=False)[:1200])
    dec = p.get("emotion_decoder") or []
    if dec:
        L.append("emotion_decoder(条数): %d" % len(dec))
    nodes = m.get("nodes") or []
    L.append("记忆节点数: %d（原文锚点保留在旧产物中，本模板不需要读取）" % len(nodes))
    return "\n".join(L)


# ---------- 离线启发式升级（无 key 验证管线用；era 从 timeline 推导） ----------
def offline_upgrade(merged):
    p = merged.get("persona") or {}
    m = merged.get("memories") or {}
    expr = p.get("expression") or {}
    emo = p.get("emotion") or {}
    rel = p.get("relationship") or {}
    tl = m.get("timeline") or []

    eras = []
    for i, s in enumerate(tl):
        if not isinstance(s, dict):
            continue
        eras.append({
            "name": s.get("stage") or "时段%d" % (i + 1),
            "start": s.get("start") or "不确定",
            "end": s.get("end") or "不确定",
            "summary": "（离线升级：%s，温度 %s）" % (
                s.get("stage", "?"), s.get("temperature", "?")),
            "catchphrases": [c.get("phrase") for c in
                             (expr.get("catchphrases") or [])[:3]],
            "greetings": {"对用户的称呼": "（未提取，待 API 升级）",
                          "自称": "（未提取）"},
            "sentence_length": {"median_chars":
                                (expr.get("sentence_length") or {}).get(
                                    "median_chars"),
                                "style": (expr.get("sentence_length") or {}).get(
                                    "style", "（未提取）")},
            "emotion_pattern": emo.get("expression_style") or "（未提取）",
            "night_behavior": "（离线升级未提取，待 API 升级）",
        })

    # evolution：timeline 相邻温度差 → 温度维度；stage_changes → 各维度
    evolution = []
    temps = [s.get("temperature") for s in tl if isinstance(s, dict)
             and s.get("temperature")]
    if len(temps) >= 2:
        evolution.append({"dimension": "温度", "from": temps[0],
                          "to": temps[-1], "stable": len(set(temps)) == 1})
    for sc in (rel.get("stage_changes") or [])[:4]:
        if isinstance(sc, dict):
            evolution.append({"dimension": sc.get("stage", "阶段"),
                              "from": sc.get("change", ""),
                              "to": "（离线升级未提取）", "stable": False})

    core = {"stable_traits": [t.get("trait") if isinstance(t, dict) else t
                              for t in (p.get("core_traits") or [])],
            "note": "（离线升级：core 沿用已有 core_traits，待 API 升级提炼）"}

    user_profile = {
        "speaking_style": "（离线升级未提取）",
        "how_she_calls_user": ["（未提取，待 API 升级）"],
        "role_in_relationship": "（离线升级未提取）",
        "shared_topics": [],
        "evidence": "无",
        "evidence_level": "impression",
    }
    return {"eras": eras, "core": core, "evolution": evolution,
            "user_profile": user_profile,
            "generation_suffix": "offline-heuristic-upgrade"}


# ---------- 主流程 ----------
def run_upgrade(merged, stats=None, prompts_dir="", offline=False):
    """返回 (new_fields, generation_suffix)。不修改输入 merged。"""
    tv = detect_template_version(merged)
    if tv >= TEMPLATE_VERSION:
        return None, ""
    if offline:
        return offline_upgrade(merged), "offline-heuristic-upgrade"
    base, key, model = api_config()
    if not key:
        raise RuntimeError(
            "未检测到 LLM_API_KEY 环境变量（可加 --offline 用启发式升级验证管线）")
    tpl_path = os.path.join(prompts_dir, "upgrade.md")
    if not os.path.isfile(tpl_path):
        raise FileNotFoundError("缺少模板: %s" % tpl_path)
    with open(tpl_path, "r", encoding="utf-8") as f:
        tpl = f.read()
    summary = build_old_summary(merged)
    stats_txt = stats_summary(stats) if stats else "（未提供统计摘要）"
    era_stats = json.dumps(
        per_era_stats(merged.get("corpus") or [],
                      (merged.get("memories") or {}).get("timeline") or []),
        ensure_ascii=False, indent=2) or "[]"
    prompt = (tpl.replace("{{OLD_SUMMARY}}", summary)
                 .replace("{{STATS}}", stats_txt)
                 .replace("{{PER_ERA_STATS}}", era_stats))
    fields = with_retry(call_json, base, key, model,
                        [{"role": "user", "content": prompt}])
    for k in ("eras", "core", "evolution", "user_profile"):
        if k not in fields:
            fields[k] = {"note": "升级未返回 %s，已留空" % k} if k != "eras" \
                else []
    return fields, "api-upgrade"


def apply_upgrade(merged, fields):
    """把增量层写回 merged（新 dict），corpus/stats/segments 原样保留。"""
    out = json.loads(json.dumps(merged))  # 深拷贝，不动输入
    p = out.setdefault("persona", {})
    p["eras"] = fields.get("eras") or []
    p["core"] = fields.get("core") or {"stable_traits": [], "note": ""}
    p["evolution"] = fields.get("evolution") or []
    out["user_profile"] = fields.get("user_profile") or {}
    out["template_version"] = TEMPLATE_VERSION
    out["upgraded_from"] = detect_template_version(merged)
    gen = out.get("generation") or "api"
    out["generation"] = gen + "+" + fields.get("generation_suffix", "upgrade")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="溯洄 · v3 增量升级（不重跑全量）")
    ap.add_argument("merged", help="旧 merged.json（distill.py 输出）")
    ap.add_argument("--stats", default="", help="stats.json（可选，增强 era 划分）")
    ap.add_argument("--out", default="", help="输出路径（默认原地覆盖）")
    ap.add_argument("--offline", action="store_true",
                    help="离线启发式升级（无 key 验证管线用，低质量）")
    ap.add_argument("--prompts", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "prompts"),
        help="prompts/ 目录（默认 ../prompts）")
    args = ap.parse_args(argv)

    with open(args.merged, "r", encoding="utf-8") as f:
        merged = json.load(f)

    tv = detect_template_version(merged)
    if tv >= TEMPLATE_VERSION:
        print("已是 v3 产物（template_version=%d），无需升级。" % tv)
        return 0

    stats = None
    if args.stats and os.path.isfile(args.stats):
        with open(args.stats, "r", encoding="utf-8") as f:
            stats = json.load(f)

    corpus_before = len(merged.get("corpus") or [])
    fields, gen = run_upgrade(merged, stats, args.prompts, args.offline)
    if fields is None:
        return 0
    out = apply_upgrade(merged, fields)
    corpus_after = len(out.get("corpus") or [])

    assert corpus_after == corpus_before, "corpus 不得因升级改变"
    out_path = args.out or args.merged
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("升级完成：%s → %s（%s）" % (args.merged, out_path, gen))
    print("  增量层: eras=%d core=%d evolution=%d user_profile=%s"
          % (len(out["persona"].get("eras") or []),
             len((out["persona"].get("core") or {}).get("stable_traits") or []),
             len(out["persona"].get("evolution") or []),
             "有" if out.get("user_profile") else "无"))
    print("  已保留: corpus=%d 条、stats、segments（未重跑全量蒸馏）" % corpus_after)
    return 0


if __name__ == "__main__":
    sys.exit(main())
