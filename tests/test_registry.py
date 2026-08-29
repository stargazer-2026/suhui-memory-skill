# -*- coding: utf-8 -*-
"""registry.py 单测（v3 多人物平台）——全部使用占位符数据（铁律：零真实数据）。"""
import json
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import registry  # noqa: E402


def make_product(tmp_path, slug="ke-du-niang", name="可嘟娘",
                 template_version=3, eras=4, standalone=True):
    """构造一个占位符人物包目录。"""
    d = tmp_path / slug
    d.mkdir()
    meta = {"name": name, "slug": slug, "template_version": template_version}
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False),
                                 encoding="utf-8")
    merged = {"name": name, "summary": "占位符人物",
              "template_version": template_version,
              "persona": {"eras": [{"name": "时段%d" % i} for i in range(eras)],
                          "core_traits": []},
              "corpus": []}
    (d / "merged.json").write_text(json.dumps(merged, ensure_ascii=False),
                                   encoding="utf-8")
    (d / "persona.md").write_text("# 人格档案（占位符）\n", encoding="utf-8")
    (d / "memories.md").write_text("# 记忆档案（占位符）\n", encoding="utf-8")
    if standalone:
        (d / "SKILL.md").write_text(
            "---\nname: %s\ndescription: 占位符\n---\n" % slug, encoding="utf-8")
    return str(d)


def run_registry(argv, capsys=None):
    return registry.main(argv)


# ---------- init / register / list / switch ----------
def test_init_creates_platform(tmp_path):
    pd = str(tmp_path / "platform")
    assert registry.main(["init", "--dir", pd]) == 0
    assert os.path.isdir(os.path.join(pd, "characters"))
    assert os.path.isfile(os.path.join(pd, "registry.json"))


def test_register_first_is_default(tmp_path):
    pd = str(tmp_path / "platform")
    registry.main(["init", "--dir", pd])
    prod = make_product(tmp_path)
    assert registry.main(["register", prod, "--dir", pd,
                          "--desc", "占位符人物", "--relation", "熟人"]) == 0
    reg = registry.load_registry(pd)
    assert len(reg["characters"]) == 1
    assert reg["active"] == "ke-du-niang"          # 单人物自动为默认人物
    c = reg["characters"][0]
    assert c["name"] == "可嘟娘" and c["relation"] == "熟人"
    assert c["template_version"] == 3 and c["eras"] == 4


def test_register_v2_product_compat(tmp_path):
    """v1/v2 旧产物目录可直接注册（template_version=1，标注可升级）。"""
    pd = str(tmp_path / "platform")
    registry.main(["init", "--dir", pd])
    prod = make_product(tmp_path, template_version=1, eras=0)
    registry.main(["register", prod, "--dir", pd])
    c = registry.load_registry(pd)["characters"][0]
    assert c["template_version"] == 1
    assert c["eras"] == 0


def test_list_and_switch(tmp_path):
    pd = str(tmp_path / "platform")
    registry.main(["init", "--dir", pd])
    a = make_product(tmp_path, slug="person-a", name="人物A")
    b = make_product(tmp_path, slug="person-b", name="人物B")
    registry.main(["register", a, "--dir", pd, "--relation", "陌生"])
    registry.main(["register", b, "--dir", pd, "--relation", "旧怨"])
    assert registry.main(["switch", "人物B", "--dir", pd]) == 0
    reg = registry.load_registry(pd)
    assert reg["active"] == "person-b"
    # list 不报错
    assert registry.main(["list", "--dir", pd]) == 0
    assert registry.main(["show", "person-a", "--dir", pd]) == 0


def test_relation_validation(tmp_path):
    pd = str(tmp_path / "platform")
    registry.main(["init", "--dir", pd])
    prod = make_product(tmp_path)
    # 非法关系 → argparse 拒绝（choices）
    with pytest.raises(SystemExit):
        registry.main(["register", prod, "--dir", pd,
                       "--relation", "不存在的关系"])


def test_duplicate_register_requires_force(tmp_path):
    pd = str(tmp_path / "platform")
    registry.main(["init", "--dir", pd])
    prod = make_product(tmp_path)
    assert registry.main(["register", prod, "--dir", pd]) == 0
    assert registry.main(["register", prod, "--dir", pd]) == 1   # 重复 → 拒绝
    assert registry.main(["register", prod, "--dir", pd,
                          "--force"]) == 0                       # --force 覆盖


# ---------- export / import（zip 往返） ----------
def test_export_import_roundtrip(tmp_path):
    pd = str(tmp_path / "platform")
    registry.main(["init", "--dir", pd])
    prod = make_product(tmp_path, slug="export-me")
    registry.main(["register", prod, "--dir", pd])
    zip_path = str(tmp_path / "export-me.zip")
    assert registry.main(["export", "export-me", zip_path,
                          "--dir", pd]) == 0
    assert os.path.isfile(zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        assert any(n.startswith("export-me/") for n in names)
        assert any(n.endswith("persona.md") for n in names)

    # 导入到另一个平台目录
    pd2 = str(tmp_path / "platform2")
    registry.main(["init", "--dir", pd2])
    assert registry.main(["import", zip_path, "--dir", pd2]) == 0
    reg2 = registry.load_registry(pd2)
    assert len(reg2["characters"]) == 1
    assert reg2["active"] == "export-me"          # 首个人物自动默认
    assert os.path.isfile(os.path.join(
        pd2, "characters", "export-me", "persona.md"))


def test_remove_keeps_files(tmp_path):
    pd = str(tmp_path / "platform")
    registry.main(["init", "--dir", pd])
    prod = make_product(tmp_path)
    registry.main(["register", prod, "--dir", pd])
    assert registry.main(["remove", "ke-du-niang", "--dir", pd]) == 0
    reg = registry.load_registry(pd)
    assert reg["characters"] == [] and reg["active"] == ""
    # 文件保留（--delete 才删）
    assert os.path.isdir(prod)


def test_show_v2_notes_upgradable(tmp_path, capsys):
    pd = str(tmp_path / "platform")
    registry.main(["init", "--dir", pd])
    prod = make_product(tmp_path, template_version=1, eras=0)
    registry.main(["register", prod, "--dir", pd])
    registry.main(["show", "ke-du-niang", "--dir", pd])
    out = capsys.readouterr().out
    assert "增量升级" in out
