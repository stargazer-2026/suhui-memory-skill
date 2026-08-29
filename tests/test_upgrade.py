# -*- coding: utf-8 -*-
"""upgrade.py 单测（v3 增量升级）——全部使用占位符数据（铁律：零真实数据）。"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import upgrade  # noqa: E402


def make_v2_merged(tmp_path, with_timeline=True):
    """构造 v2 产物（无 template_version / 无 eras / 无 user_profile）。"""
    merged = {
        "summary": "占位符人物的一句话",
        "version": 1,
        "name": "可嘟娘",
        "generation": "api",
        "persona": {
            "core_traits": [{"trait": "被动但渴望被找", "evidence_level": "impression"}],
            "expression": {
                "catchphrases": [{"phrase": "害", "freq": 3, "when": "日常"}],
                "sentence_length": {"median_chars": 12, "style": "短句多"},
            },
            "emotion": {"expression_style": "嘴硬心软"},
            "relationship": {"stage_changes": [
                {"stage": "热恋期", "change": "称呼变亲昵", "evidence": "占位符"}]},
        },
        "memories": {
            "timeline": [
                {"stage": "初识", "start": "2030-01", "end": "2030-03",
                 "temperature": "适中", "events": ["占位符事件1"]},
                {"stage": "热恋", "start": "2030-04", "end": "2030-06",
                 "temperature": "偏热", "events": ["占位符事件2"]},
            ],
            "nodes": [{"event": "占位符节点", "evidence": "原文占位符"}],
        },
        "entity_clusters": [],
        "conflicts": [],
        "corrections": [],
        "corpus": [{"ts": "2030-01-01T10:00:00", "sender": "B", "text": "占位符原话"}]
        * 3,
        "stats": {"total_messages": 3},
        "segment_count": 1,
    }
    if not with_timeline:
        merged["memories"]["timeline"] = []
    return merged


# ---------- 版本检测 ----------
def test_detect_template_version():
    assert upgrade.detect_template_version({}) == 1          # 旧产物无字段 → v1
    assert upgrade.detect_template_version({"template_version": 2}) == 2
    assert upgrade.detect_template_version({"template_version": 3}) == 3


def test_already_v3_noop(tmp_path):
    m = make_v2_merged(tmp_path)
    m["template_version"] = 3
    p = tmp_path / "merged.json"
    p.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    assert upgrade.main([str(p)]) == 0
    # 文件未被改写（无 template_version=3 的重复写入）
    after = json.loads(p.read_text(encoding="utf-8"))
    assert after["template_version"] == 3


# ---------- 离线升级（启发式） ----------
def test_offline_upgrade_derives_eras(tmp_path):
    m = make_v2_merged(tmp_path)
    fields, gen = upgrade.run_upgrade(m, offline=True)
    assert gen == "offline-heuristic-upgrade"
    assert len(fields["eras"]) == 2                      # timeline 2 段
    assert fields["eras"][0]["name"] == "初识"
    assert fields["eras"][0]["greetings"]["对用户的称呼"]      # 占位字段
    assert fields["eras"][1]["greetings"]["对用户的称呼"]
    assert fields["evolution"]                                  # 温度变化 → 演变
    assert fields["user_profile"]["evidence_level"] == "impression"


def test_apply_upgrade_preserves_corpus_and_adds_fields(tmp_path):
    m = make_v2_merged(tmp_path)
    fields, gen = upgrade.run_upgrade(m, offline=True)
    out = upgrade.apply_upgrade(m, fields)
    assert out["template_version"] == 3
    assert out["upgraded_from"] == 1
    assert "api+offline-heuristic-upgrade" in out["generation"]
    assert len(out["persona"]["eras"]) == 2
    assert out["persona"]["core"]["stable_traits"]          # 沿用 core_traits
    assert out["user_profile"]["how_she_calls_user"]
    assert len(out["corpus"]) == len(m["corpus"])           # corpus 原样
    assert out["corpus"] == m["corpus"]
    # 旧字段全部保留
    assert out["persona"]["expression"]["catchphrases"][0]["phrase"] == "害"
    assert out["memories"]["nodes"][0]["evidence"] == "原文占位符"


def test_upgrade_main_offline(tmp_path):
    m = make_v2_merged(tmp_path)
    p = tmp_path / "merged.json"
    p.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    assert upgrade.main([str(p), "--offline"]) == 0
    after = json.loads(p.read_text(encoding="utf-8"))
    assert after["template_version"] == 3
    assert len(after["persona"]["eras"]) == 2
    assert len(after["corpus"]) == 3


# ---------- API 升级：单次 merge 级调用（不重跑全量） ----------
def test_api_upgrade_single_call_no_redistill(tmp_path, monkeypatch):
    """核心验收：--upgrade 只调 1 次 LLM（≈全量 5%），不重新逐段蒸馏。"""
    m = make_v2_merged(tmp_path)
    calls = []

    def fake_call_json(base, key, model, messages, temperature=0.3):
        calls.append(messages)
        return {
            "eras": [{"name": "初识", "start": "2030-01", "end": "2030-03",
                      "summary": "刚认识的她", "catchphrases": ["hi"],
                      "greetings": {"对用户的称呼": "喂", "自称": "我"},
                      "sentence_length": {"median_chars": 10, "style": "短句"},
                      "emotion_pattern": "客气", "night_behavior": "偶尔熬夜"}],
            "core": {"stable_traits": ["被动但渴望被找"],
                     "note": "本质上是个嘴硬心软的人"},
            "evolution": [{"dimension": "称呼", "from": "喂", "to": "亲爱的",
                           "stable": False}],
            "user_profile": {"speaking_style": "话多且碎",
                             "how_she_calls_user": ["喂", "亲爱的"],
                             "role_in_relationship": "倾听者",
                             "shared_topics": ["猫", "深夜聊天"],
                             "evidence": "无", "evidence_level": "impression"},
        }

    monkeypatch.setattr(upgrade, "api_config",
                        lambda: ("http://mock.local/v1", "fake-key", "mock-model"))
    monkeypatch.setattr(upgrade, "call_json", fake_call_json)
    prompts_dir = os.path.join(os.path.dirname(__file__), "..", "prompts")
    fields, gen = upgrade.run_upgrade(m, stats=m.get("stats"),
                                      prompts_dir=prompts_dir)
    assert gen == "api-upgrade"
    assert len(calls) == 1                                   # 只调 1 次
    assert fields["eras"][0]["greetings"]["对用户的称呼"] == "喂"
    # 模板输入不包含逐段原文（不重新蒸馏的证明：摘要不含 corpus 原文）
    prompt = calls[0][0]["content"]
    assert "占位符原话" not in prompt
    assert "记忆节点数" in prompt


def test_api_upgrade_requires_key(tmp_path):
    m = make_v2_merged(tmp_path)
    monkeypatch_clear_key = pytest.MonkeyPatch()
    monkeypatch_clear_key.delenv("LLM_API_KEY", raising=False)
    try:
        with pytest.raises(RuntimeError, match="LLM_API_KEY"):
            upgrade.run_upgrade(m, prompts_dir=str(tmp_path))
    finally:
        monkeypatch_clear_key.undo()


def test_upgrade_offline_no_timeline(tmp_path):
    m = make_v2_merged(tmp_path, with_timeline=False)
    fields, _gen = upgrade.run_upgrade(m, offline=True)
    assert fields["eras"] == []
    # 无 timeline → 无温度维度演变；stage_changes 维度仍可推导
    assert all(e["dimension"] != "温度" for e in fields["evolution"])


# ---------- 分时段口癖统计（artifact 证据，时段划分辅助） ----------
def test_per_era_stats_artifact(tmp_path):
    corpus = [
        {"ts": "2030-01-10", "sender": "B", "text": "嘿嘿 今天好累啊"},
        {"ts": "2030-02-10", "sender": "B", "text": "嘿嘿 晚安"},
        {"ts": "2030-03-10", "sender": "B", "text": "晚安"},
    ]
    tl = [{"stage": "初识", "start": "2030-01", "end": "2030-02"},
          {"stage": "热恋", "start": "2030-02", "end": "2030-04"}]
    rows = upgrade.per_era_stats(corpus, tl)
    assert len(rows) == 2
    assert rows[0]["stage"] == "初识" and rows[0]["messages_B"] == 1
    assert rows[0]["top_phrases_B"][0]["phrase"] == "嘿嘿"
    assert rows[1]["top_phrases_B"][0]["phrase"] == "晚安"
    assert upgrade.per_era_stats(corpus, []) == []
    assert upgrade.per_era_stats([], tl) == []


def test_per_segment_stats_artifact():
    import distill
    segs = [{"id": 0, "start": "2030-01", "end": "2030-02",
             "messages": [{"sender": "B", "text": "害 今天好累 好累"},
                          {"sender": "A", "text": "早点睡"}]}]
    rows = distill.per_segment_stats(segs)
    assert rows[0]["messages_B"] == 1
    assert rows[0]["top_phrases_B"][0]["phrase"] == "好累"
