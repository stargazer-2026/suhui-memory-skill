# -*- coding: utf-8 -*-
"""平台 SKILL.md 兼容性 + build.py v3 产物测试——全部使用占位符数据。"""
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import build  # noqa: E402
from theater import FICTIONAL_MARKER, FICTIONAL_LINE  # noqa: E402

PLATFORM_SKILL = os.path.join(os.path.dirname(__file__), "..", "SKILL.md")


def make_v3_merged():
    return {
        "summary": "占位符人物的一句话",
        "name": "可嘟娘",
        "template_version": 3,
        "generation": "offline-heuristic",
        "coverage": "full",
        "persona": {
            "core_traits": [{"trait": "被动但渴望被找", "evidence_level": "impression"}],
            "eras": [
                {"name": "初识", "start": "2030-01", "end": "2030-03",
                 "summary": "刚认识的她", "catchphrases": ["hi"],
                 "greetings": {"对用户的称呼": "喂", "自称": "我"},
                 "sentence_length": {"median_chars": 10, "style": "短句多"},
                 "emotion_pattern": "客气", "night_behavior": "偶尔熬夜"},
                {"name": "热恋", "start": "2030-04", "end": "2030-06",
                 "summary": "黏人的她", "catchphrases": ["嘿嘿"],
                 "greetings": {"对用户的称呼": "亲爱的", "自称": "人家"},
                 "sentence_length": {"median_chars": 18, "style": "碎句多"},
                 "emotion_pattern": "热烈", "night_behavior": "深夜话多"},
            ],
            "core": {"stable_traits": ["嘴硬心软"], "note": "本质上是个温柔的人"},
            "evolution": [{"dimension": "称呼", "from": "喂", "to": "亲爱的",
                           "stable": False}],
            "expression": {"catchphrases": [{"phrase": "害", "freq": 2,
                                             "when": "日常", "examples": []}]},
        },
        "memories": {"timeline": [], "nodes": [], "daily_patterns": [],
                     "unfinished": []},
        "entity_clusters": [],
        "conflicts": [],
        "corrections": [],
        "user_profile": {
            "speaking_style": "话多且碎",
            "how_she_calls_user": ["喂", "亲爱的"],
            "role_in_relationship": "倾听者",
            "shared_topics": ["猫", "深夜聊天"],
            "evidence": "无",
            "evidence_level": "impression",
        },
        "corpus": [],
        "stats": {},
        "segment_count": 0,
    }


def build_product(tmp_path, merged=None, version="pro", name="可嘟娘",
                  slug="ke-du-niang"):
    merged = merged or make_v3_merged()
    p = tmp_path / "merged.json"
    p.write_text(json.dumps(merged, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "out"
    assert build.main([str(p), "--out", str(out), "--name", name,
                       "--slug", slug, "--version", version]) == 0
    return out


# ---------- 平台 SKILL.md 兼容性（Vercel skills 生态不回归） ----------
def test_platform_frontmatter_compat():
    """name+description frontmatter 必须保持（Vercel npx skills add 兼容）。"""
    text = open(PLATFORM_SKILL, encoding="utf-8").read()
    assert text.startswith("---\n")
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    assert m
    fm = m.group(1)
    assert re.search(r"^name: suhui\s*$", fm, re.M)
    assert re.search(r"^description: ", fm, re.M)
    # 增量 metadata 不破坏解析：author/version 以平铺 key 追加
    assert "author: stargazer-2026" in fm
    assert "version: 3.0.2" in fm


def test_platform_intent_mapping_present():
    """自然语言意图映射表（主交互）必须在 SKILL.md 中。"""
    text = open(PLATFORM_SKILL, encoding="utf-8").read()
    assert "我想跟 X 说话" in text and "X 在吗" in text
    assert "让 X 和 Y 聊聊" in text
    assert "回到我们刚认识的时候" in text
    assert "她那时候怎么叫我" in text
    assert "她怎么看我" in text
    assert "自然语言意图映射" in text


def test_platform_theater_sections():
    text = open(PLATFORM_SKILL, encoding="utf-8").read()
    assert "满血版" in text and "残血版" in text
    assert "subagent" in text and "单会话双人格" in text
    assert "开场温度" in text and "陌生" in text and "旧怨" in text
    assert "虚构隔离" in text
    assert "不进真实记忆库" in text


def test_platform_multi_character_sections():
    text = open(PLATFORM_SKILL, encoding="utf-8").read()
    assert "characters/" in text and "registry.json" in text
    assert "增量升级" in text and "upgrade.py" in text
    assert "时段化人格" in text and "user_profile" in text


def test_platform_run_rule3_tool_retrieval():
    """运行规则 3（再取记忆）必须指向 storage.py query 工具调用 + 降级路径
    （v3.0.2：对话层接通记忆库检索，不靠 prompt 记忆）。"""
    text = open(PLATFORM_SKILL, encoding="utf-8").read()
    assert "再取记忆" in text
    assert "storage.py query" in text
    assert "--topk 5" in text
    # 三处降级：库未建 / shell 不可用 / 查询失败
    assert "记忆库未建，已降级" in text
    assert "静默降级" in text
    assert "不报错、不打断" in text
    # 调用 shell 工具（跨场景通用，不特化运行时）
    assert "shell 工具" in text


def test_platform_flow_step45_build_library():
    """首次引导流程 Step 4.5：建记忆库（init/import），对话层检索才能生效。"""
    text = open(PLATFORM_SKILL, encoding="utf-8").read()
    assert "Step 4.5" in text
    assert "storage.py init" in text
    assert "storage.py import" in text
    assert "entity_clusters.json" in text
    # 建库失败不阻塞：对话降级为 prompt 记忆
    assert "降级" in text


def test_theater_fictional_markers():
    assert "虚构" in FICTIONAL_MARKER and "fictional" in FICTIONAL_MARKER
    assert "不进真实记忆库" in FICTIONAL_LINE


# ---------- build.py v3：时段化人格 / 用户侧画像 / 兼容 ----------
def test_build_v3_persona_has_eras_and_evolution(tmp_path):
    out = build_product(tmp_path)
    persona = (out / "persona.md").read_text(encoding="utf-8")
    assert "## 时段化人格（eras，v3）" in persona
    assert "时段 1 · 初识" in persona and "时段 2 · 热恋" in persona
    assert "对用户的称呼" in persona and "亲爱的" in persona
    assert "## 演变轨迹（evolution，v3）" in persona
    assert "称呼" in persona
    assert "## 核心稳定特质（core，v3" in persona
    assert "最新时段: 热恋" in persona          # 默认最新时段


def test_build_v3_user_profile_md(tmp_path):
    out = build_product(tmp_path)
    up = (out / "user_profile.md").read_text(encoding="utf-8")
    assert "用户侧画像" in up
    assert "不是可对话角色" in up
    assert "话多且碎" in up
    assert "共同话题" in up and "猫" in up


def test_build_v3_meta(tmp_path):
    out = build_product(tmp_path)
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["template_version"] == 3
    assert meta["eras"] == 2
    assert meta["has_user_profile"] is True


def test_build_v2_merged_compat(tmp_path):
    """v2 产物（无 eras/user_profile）仍可 build（v3 读取旧产物兼容）。"""
    m = make_v3_merged()
    m["template_version"] = 1
    m["persona"].pop("eras")
    m["persona"].pop("core")
    m["persona"].pop("evolution")
    m.pop("user_profile")
    out = build_product(tmp_path, merged=m)
    persona = (out / "persona.md").read_text(encoding="utf-8")
    assert "时段化人格" not in persona          # 无 eras → 不渲染该节
    assert "Layer 0" in persona                 # 旧字段照常
    up = (out / "user_profile.md").read_text(encoding="utf-8")
    assert "未含用户侧画像" in up               # 占位说明
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["template_version"] == 1
    assert meta["has_user_profile"] is False


def test_build_flash_80_cut(tmp_path):
    """flash 版：保留核心（时段切换/剧场残血/多人物），裁掉边际机制。"""
    out = build_product(tmp_path, version="flash")
    skill = (out / "SKILL.md").read_text(encoding="utf-8")
    assert "时段化人格（v3）" in skill          # 保留
    assert "用户侧画像（user_profile.md）" in skill  # 保留
    assert "三通道混合检索出原话作锚点" in skill      # 保留（80% 核心）
    assert "竞争性干扰" not in skill            # 裁掉
    assert "多路径择优" not in skill            # 裁掉
    assert "PAD" not in skill                   # 裁掉三维动力学
    assert "世界树打分公式" not in skill
    # flash 功能清单 ≤ 10 项（80% 原则：8-10 核心）
    feats = re.findall(r"^- (人格|记忆|表达|时段化|多人物|剧场|连续|流程|访谈)",
                       skill, re.M)
    assert len(feats) <= 10 and len(feats) >= 5
    assert "「这个我没装，换完整版就能用」" in skill  # 诚实降级声明


def test_build_pro_keeps_full(tmp_path):
    out = build_product(tmp_path, version="pro")
    skill = (out / "SKILL.md").read_text(encoding="utf-8")
    assert "战略休眠与唤醒（4.46）" in skill    # pro 全量
    assert "PAD" in skill


def test_build_character_frontmatter_compat(tmp_path):
    """人物包 SKILL.md 保持 name+description（Vercel 兼容不回归）。"""
    out = build_product(tmp_path)
    skill = (out / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", skill, re.S)
    assert m
    assert re.search(r"^name: ke-du-niang\s*$", m.group(1), re.M)
    assert re.search(r"^description: ", m.group(1), re.M)


# ---------- theater.py：虚构隔离 ----------
def _make_platform_with_chars(tmp_path):
    """注册两个人物的平台（占位符）。"""
    import registry
    pd = str(tmp_path / "platform")
    registry.main(["init", "--dir", pd])
    for slug, name, rel in (("person-a", "人物A", "熟人"),
                            ("person-b", "人物B", "陌生")):
        d = tmp_path / slug
        d.mkdir()
        (d / "meta.json").write_text(
            json.dumps({"name": name, "slug": slug,
                        "template_version": 3}),
            encoding="utf-8")
        (d / "merged.json").write_text(
            json.dumps({"name": name, "template_version": 3,
                        "persona": {"eras": []}}), encoding="utf-8")
        (d / "persona.md").write_text("# 占位符\n", encoding="utf-8")
        (d / "memories.md").write_text("# 占位符\n", encoding="utf-8")
        (d / "SKILL.md").write_text("---\nname: %s\ndescription: 占位\n---\n"
                                    % slug, encoding="utf-8")
        registry.main(["register", str(d), "--dir", pd,
                       "--relation", rel])
    return pd


def test_theater_script_fictional_and_isolated(tmp_path):
    import theater
    pd = _make_platform_with_chars(tmp_path)
    assert theater.main(["script", "person-a", "person-b", "--dir", pd]) == 0
    scripts = list((tmp_path / "platform" / "theater").glob("*.md"))
    assert len(scripts) == 1
    text = scripts[0].read_text(encoding="utf-8")
    assert FICTIONAL_MARKER in text            # 虚构声明
    assert "虚构演绎" in text
    assert "人物A" in text and "人物B" in text
    assert "开场温度" in text
    # 虚构隔离：人物记忆库未被触碰
    mem_a = (tmp_path / "platform" / "characters" / "person-a"
             / "memories.md").read_text(encoding="utf-8")
    assert mem_a == "# 占位符\n"


def test_theater_rejects_unregistered(tmp_path):
    import theater
    pd = _make_platform_with_chars(tmp_path)
    assert theater.main(["script", "person-a", "陌生人丙", "--dir", pd]) == 1
    assert theater.main(["script", "person-a", "person-a", "--dir", pd]) == 1


def test_theater_stamp_adds_marker_once(tmp_path):
    import theater
    f = tmp_path / "draft.md"
    f.write_text("# 草稿\n", encoding="utf-8")
    assert theater.main(["stamp", str(f)]) == 0
    text = f.read_text(encoding="utf-8")
    assert FICTIONAL_MARKER in text
    assert theater.main(["stamp", str(f)]) == 0   # 幂等
    assert text == f.read_text(encoding="utf-8")

