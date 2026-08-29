# -*- coding: utf-8 -*-
"""distill.py 单测（v3.0.1 合并完整性守卫）——全部使用占位符数据（铁律：零真实数据）。

覆盖：
  - merge 返回完整 v3 字段（eras + user_profile）→ template_version=3，无警告
  - merge 缺 eras / 缺 user_profile（任一）→ template_version=2 + stderr 警告
    （降级后 upgrade.py 可增量补齐，防止被 >=3 跳过而永久缺失）
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import distill  # noqa: E402

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "prompts")


def make_inputs(tmp_path):
    """构造 segments.json / stats.json（占位符）。"""
    segments = {
        "segments": [{
            "id": 0, "start": "2030-01", "end": "2030-03", "count": 2,
            "messages": [
                {"ts": "2030-01-01T10:00:00", "sender": "A", "text": "占位符A"},
                {"ts": "2030-01-01T10:01:00", "sender": "B", "text": "占位符B你好"},
            ],
        }]
    }
    (tmp_path / "segments.json").write_text(
        json.dumps(segments, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "stats.json").write_text("{}", encoding="utf-8")
    return tmp_path / "segments.json", tmp_path / "stats.json"


def make_merged_response(with_eras=True, with_profile=True):
    """merge 阶段 LLM 返回（占位符）。"""
    persona = {
        "core_traits": [{"trait": "被动但渴望被找", "evidence_level": "impression"}],
        "expression": {"catchphrases": []},
        "emotion": {"day_night": []},
        "relationship": {},
        "values": [],
        "speculative": [],
    }
    if with_eras:
        persona["eras"] = [{"name": "初识", "greetings": {"对用户的称呼": "喂"}}]
    merged = {
        "summary": "占位符人物的一句话",
        "persona": persona,
        "memories": {"timeline": [], "nodes": [], "daily_patterns": [],
                     "unfinished": []},
        "entity_clusters": [],
        "conflicts": [],
    }
    if with_profile:
        merged["user_profile"] = {"speaking_style": "话多且碎",
                                  "how_she_calls_user": ["喂"],
                                  "evidence_level": "impression"}
    return merged


def run_distill_main(tmp_path, monkeypatch, **merged_kw):
    """跑 distill.main()：段蒸馏用假 call_json，merge 返回 merged_kw 定制的响应。"""
    segs_path, stats_path = make_inputs(tmp_path)
    persona_resp = make_merged_response(with_eras=True, with_profile=True)["persona"]
    memories_resp = {"timeline": [{"stage": "初识"}], "nodes": [],
                     "daily_patterns": [], "unfinished": [],
                     "entity_clusters": []}
    calls = []

    def fake_call_json(base, key, model, messages, temperature=0.3):
        calls.append(messages)
        if len(calls) == 1:                      # 段：persona_extract
            return persona_resp
        if len(calls) == 2:                      # 段：memories_extract
            return memories_resp
        return make_merged_response(**merged_kw)  # 合并：merge.md

    monkeypatch.setattr(distill, "api_config",
                        lambda: ("http://mock.local/v1", "fake-key", "mock-model"))
    monkeypatch.setattr(distill, "call_json", fake_call_json)
    rc = distill.main([str(segs_path), str(stats_path), PROMPTS_DIR,
                       "--out", str(tmp_path / "out"), "--name", "占位符"])
    merged_path = tmp_path / "out" / "merged.json"
    with open(merged_path, "r", encoding="utf-8") as f:
        merged = json.load(f)
    return rc, merged, calls


# ---------- 完整 v3 字段 → template_version=3，无警告 ----------
def test_merge_full_v3_fields_keeps_v3(tmp_path, monkeypatch, capsys):
    rc, merged, calls = run_distill_main(tmp_path, monkeypatch,
                                         with_eras=True, with_profile=True)
    assert rc == 0
    assert merged["template_version"] == 3
    assert merged["persona"]["eras"]          # 保留
    assert merged["user_profile"]             # 保留
    assert "⚠" not in capsys.readouterr().err


# ---------- 缺 eras → 降级 v2 + 警告 ----------
def test_merge_missing_eras_downgrades_to_v2(tmp_path, monkeypatch, capsys):
    rc, merged, calls = run_distill_main(tmp_path, monkeypatch,
                                         with_eras=False, with_profile=True)
    assert rc == 0
    assert merged["template_version"] == 2         # 降级 → upgrade.py 可救回
    assert "user_profile" in merged
    err = capsys.readouterr().err
    assert "merge 未返回完整 v3 字段" in err
    assert "eras=False" in err and "user_profile=True" in err
    assert "upgrade.py 增量补齐" in err


# ---------- 缺 user_profile → 降级 v2 + 警告 ----------
def test_merge_missing_profile_downgrades_to_v2(tmp_path, monkeypatch, capsys):
    rc, merged, calls = run_distill_main(tmp_path, monkeypatch,
                                         with_eras=True, with_profile=False)
    assert rc == 0
    assert merged["template_version"] == 2
    assert "eras" in merged["persona"]
    err = capsys.readouterr().err
    assert "merge 未返回完整 v3 字段" in err
    assert "eras=True" in err and "user_profile=False" in err
