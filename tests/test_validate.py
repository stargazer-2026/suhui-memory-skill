# -*- coding: utf-8 -*-
"""validate.py 单测（v3.0.1 配套）——全部使用占位符数据（铁律：零真实数据）。

覆盖：
  - v3 可选增强键（eras/core）：存在时校验类型，缺失不报错
  - 标 v3 但缺 persona.eras → 报 warning（不阻断，exit 0）
  - main() 集成：warning 不改变退出码
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import validate  # noqa: E402


def make_merged(template_version=3, eras="with"):
    """构造一份结构合法的最小 merged.json（占位符）。eras: with/absent/bad_type。"""
    persona = {
        "core_traits": [{"trait": "被动但渴望被找", "evidence_level": "impression"}],
        "expression": {"catchphrases": []},
        "emotion": {"day_night": [
            {"when": "深夜", "behavior": "占位符行为", "evidence_level": "artifact"}]},
        "relationship": {},
        "values": [],
        "speculative": [],
    }
    if eras == "with":
        persona["eras"] = [{"name": "初识", "greetings": {"对用户的称呼": "喂"}}]
    elif eras == "bad_type":
        persona["eras"] = {"name": "初识"}  # 应为 list
    return {
        "summary": "占位符人物的一句话",
        "template_version": template_version,
        "persona": persona,
        "memories": {
            "timeline": [{"stage": "初识", "start": "2030-01", "end": "2030-03"}],
            "nodes": [],
            "daily_patterns": [],
            "unfinished": [],
        },
        "entity_clusters": [],
        "conflicts": [],
    }


# ---------- 可选增强键：缺失不报错 ----------
def test_optional_keys_absent_no_problem(tmp_path):
    p = tmp_path / "merged.json"
    p.write_text(json.dumps(make_merged(template_version=2, eras="absent"),
                            ensure_ascii=False), encoding="utf-8")
    ok, problems, warnings = validate.check_json_file(str(p))
    assert ok
    assert problems == []
    assert warnings == []           # v2 缺 eras 不算问题（可选增强）


def test_optional_keys_present_with_wrong_type(tmp_path):
    p = tmp_path / "merged.json"
    p.write_text(json.dumps(make_merged(template_version=3, eras="bad_type"),
                            ensure_ascii=False), encoding="utf-8")
    ok, problems, warnings = validate.check_json_file(str(p))
    assert not ok
    assert any("persona.eras 类型应为 list" in x for x in problems)


# ---------- 标 v3 缺 eras → warning 不阻断 ----------
def test_v3_without_eras_warns_but_not_blocking(tmp_path):
    p = tmp_path / "merged.json"
    p.write_text(json.dumps(make_merged(template_version=3, eras="absent"),
                            ensure_ascii=False), encoding="utf-8")
    ok, problems, warnings = validate.check_json_file(str(p))
    assert ok                                  # 不阻断
    assert problems == []
    assert len(warnings) == 1
    assert "建议 upgrade.py 补齐" in warnings[0]
    assert "缺时段化人格" in warnings[0]


def test_v3_with_eras_no_warning(tmp_path):
    p = tmp_path / "merged.json"
    p.write_text(json.dumps(make_merged(template_version=3, eras="with"),
                            ensure_ascii=False), encoding="utf-8")
    ok, problems, warnings = validate.check_json_file(str(p))
    assert ok
    assert warnings == []


def test_v2_without_eras_no_warning(tmp_path):
    """v2 产物缺 eras 是正常形态（upgrade.py 补），不警告。"""
    p = tmp_path / "merged.json"
    p.write_text(json.dumps(make_merged(template_version=2, eras="absent"),
                            ensure_ascii=False), encoding="utf-8")
    ok, problems, warnings = validate.check_json_file(str(p))
    assert ok
    assert warnings == []


# ---------- main() 集成：warning 不改变退出码（exit 0） ----------
def test_main_exit_zero_with_warning(tmp_path, capsys):
    merged = make_merged(template_version=3, eras="absent")
    (tmp_path / "merged.json").write_text(json.dumps(merged, ensure_ascii=False),
                                          encoding="utf-8")
    assert validate.main([str(tmp_path)]) == 0   # 警告不阻断
    out = capsys.readouterr().out
    assert "✅ merged.json" in out
    assert "警告：产物标 v3" in out
    assert "1 条警告" in out
