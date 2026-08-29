#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
registry.py — 多人物注册表（v3 平台地基）

人物包 = 独立目录（persona.md / memories.md [ / worldbook.md / user_profile.md /
meta.json / merged.json …），zip 可导出/迁移/分享（隐私由用户控制）。
单人物产物（v1/v2 build.py 输出）可直接注册为默认人物——旧产物目录即人物包。

用法：
  python3 registry.py init [--dir <平台目录>]
  python3 registry.py register <人物包目录> [--name <名字>] [--desc <一句话>]
      [--relation 陌生|熟人|旧怨|其他] [--dir <平台目录>] [--force]
  python3 registry.py list [--dir <平台目录>]
  python3 registry.py show <名字|slug> [--dir <平台目录>]
  python3 registry.py switch <名字|slug> [--dir <平台目录>]     # 设为当前人物
  python3 registry.py export <名字|slug> <zip路径> [--dir <平台目录>]
  python3 registry.py import <zip路径> [--dir <平台目录>]
  python3 registry.py remove <名字|slug> [--dir <平台目录>] [--delete]

注册表行：名字 / slug / 路径 / 一句话描述 / 与用户关系（陌生/熟人/旧怨——决定剧场
第一句话的温度）/ template_version / 时段数 / 更新时间。注册表存本地 registry.json。
"""
import argparse
import datetime
import json
import os
import re
import shutil
import sys
import zipfile

REGISTRY_FILE = "registry.json"
CHARACTERS_DIR = "characters"
RELATIONS = ("陌生", "熟人", "旧怨", "其他")
TEMPLATE_VERSION = 3


def now():
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def default_platform_dir():
    return os.getcwd()


def reg_path(platform_dir):
    return os.path.join(platform_dir, REGISTRY_FILE)


def chars_dir(platform_dir):
    return os.path.join(platform_dir, CHARACTERS_DIR)


# ---------- 读写 ----------
def load_registry(platform_dir):
    p = reg_path(platform_dir)
    if not os.path.isfile(p):
        return {"format": "suhui-character-registry", "version": TEMPLATE_VERSION,
                "active": "", "characters": []}
    with open(p, "r", encoding="utf-8") as f:
        reg = json.load(f)
    reg.setdefault("characters", [])
    reg.setdefault("active", "")
    return reg


def save_registry(platform_dir, reg):
    os.makedirs(platform_dir, exist_ok=True)
    tmp = reg_path(platform_dir) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, reg_path(platform_dir))


def find_char(reg, key):
    """按 slug 或名字精确查找。"""
    for c in reg["characters"]:
        if c.get("slug") == key or c.get("name") == key:
            return c
    return None


def _char_path(platform_dir, slug):
    return os.path.join(chars_dir(platform_dir), slug)


# ---------- 人物包探测（v1/v2 产物目录兼容） ----------
def probe_product_dir(path):
    """探测目录是否可作人物包；返回 (slug, name, template_version, eras, standalone)。"""
    if not os.path.isdir(path):
        raise ValueError("人物包目录不存在: %s" % path)
    meta_path = os.path.join(path, "meta.json")
    meta = {}
    if os.path.isfile(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    slug = meta.get("slug") or os.path.basename(os.path.normpath(path))
    name = meta.get("name") or ""
    tv = int(meta.get("template_version") or
             meta.get("artifact_template_version") or 1)
    eras = 0
    merged_path = os.path.join(path, "merged.json")
    if os.path.isfile(merged_path):
        with open(merged_path, "r", encoding="utf-8") as f:
            try:
                merged = json.load(f)
                tv = int(merged.get("template_version") or tv)
                eras = len((merged.get("persona") or {}).get("eras") or [])
            except ValueError:
                pass
    standalone = os.path.isfile(os.path.join(path, "SKILL.md"))
    if not (os.path.isfile(os.path.join(path, "persona.md")) or
            os.path.isfile(os.path.join(path, "merged.json"))):
        raise ValueError("目录不是人物包（缺 persona.md 或 merged.json）: %s" % path)
    return slug, name, tv, eras, standalone


# ---------- 命令 ----------
def cmd_init(args):
    os.makedirs(chars_dir(args.dir), exist_ok=True)
    reg = load_registry(args.dir)
    save_registry(args.dir, reg)
    print("已初始化平台目录: %s（%s/ + %s）"
          % (args.dir, CHARACTERS_DIR, REGISTRY_FILE))
    return 0


def cmd_register(args):
    slug, name, tv, eras, standalone = probe_product_dir(args.product)
    # 人物包收纳进平台 characters/（已在平台内则原地引用；v1/v2 旧产物目录
    # 也可直接注册——平台取副本，旧目录不受影响）
    prod_abs = os.path.abspath(args.product)
    plat_abs = os.path.abspath(args.dir)
    if prod_abs.startswith(plat_abs + os.sep):
        entry_path = os.path.relpath(prod_abs, plat_abs)
    else:
        dest = _char_path(args.dir, slug)
        if os.path.exists(dest):
            if not args.force:
                print("目标已存在: %s。加 --force 覆盖收纳。" % dest)
                return 1
            shutil.rmtree(dest)
        shutil.copytree(prod_abs, dest,
                        ignore=shutil.ignore_patterns("snapshots",
                                                      "__pycache__"))
        entry_path = os.path.join(CHARACTERS_DIR, slug)
    reg = load_registry(args.dir)
    if find_char(reg, slug) and not args.force:
        print("已存在同名人物（slug=%s）。加 --force 覆盖注册。" % slug)
        return 1
    entry = {
        "name": args.name or name or slug,
        "slug": slug,
        "path": entry_path,
        "desc": args.desc or "",
        "relation": args.relation,          # 与用户关系 → 剧场第一句话的温度
        "template_version": tv,
        "eras": eras,
        "standalone": standalone,
        "registered": now(),
        "updated": now(),
    }
    if not reg["characters"] or not reg["active"]:
        reg["active"] = slug          # 单人物产物自动注册为默认人物（v1/v2 兼容）
    reg["characters"] = [c for c in reg["characters"] if c["slug"] != slug]
    reg["characters"].append(entry)
    save_registry(args.dir, reg)
    extra = ""
    if tv < TEMPLATE_VERSION:
        extra = "（v%d 产物，可运行 upgrade.py 增量升级到 v3 时段化人格）" % tv
    print("已注册: %s（slug=%s，关系=%s，template_version=%d，时段=%d）%s"
          % (entry["name"], slug, args.relation, tv, eras, extra))
    if reg["active"] == slug:
        print("  已设为默认人物（当前活跃）")
    return 0


def cmd_list(args):
    reg = load_registry(args.dir)
    if not reg["characters"]:
        print("注册表为空。注册第一个人物：python3 registry.py register <人物包目录>")
        print("（v1/v2 产物目录可直接注册——单人物产物自动成为默认人物）")
        return 0
    print("%-4s %-12s %-16s %-8s %-6s %s" %
          ("", "名字", "slug", "关系", "时段", "一句话描述"))
    for c in reg["characters"]:
        mark = "→" if c["slug"] == reg["active"] else " "
        tv = c.get("template_version", 1)
        tv_note = "v%d%s" % (tv, "（可升级）" if tv < TEMPLATE_VERSION else "")
        print("%-4s %-12s %-16s %-8s %-6s %s" % (
            mark, c.get("name", "?"), c.get("slug", "?"),
            c.get("relation", "其他"), tv_note, c.get("desc", "")))
    print("\n当前人物: %s（「我想跟 X 说话」加载/切换）" %
          (reg["active"] or "未设置"))
    return 0


def cmd_show(args):
    reg = load_registry(args.dir)
    c = find_char(reg, args.key)
    if not c:
        print("未找到人物: %s（先 registry.py list 查看）" % args.key)
        return 1
    print("名字: %s" % c.get("name"))
    print("slug: %s" % c.get("slug"))
    print("路径: %s" % c.get("path"))
    print("描述: %s" % (c.get("desc") or "（无）"))
    print("与用户关系: %s" % c.get("relation", "其他"))
    print("template_version: %d%s" % (
        c.get("template_version", 1),
        "（可 upgrade.py 增量升级）" if c.get("template_version", 1) < 3 else ""))
    print("时段化人格: %d 段" % c.get("eras", 0))
    print("注册: %s  更新: %s" % (c.get("registered", "?"), c.get("updated", "?")))
    return 0


def cmd_switch(args):
    reg = load_registry(args.dir)
    c = find_char(reg, args.key)
    if not c:
        print("未找到人物: %s" % args.key)
        return 1
    reg["active"] = c["slug"]
    save_registry(args.dir, reg)
    print("当前人物 → %s（%s）" % (c["name"], c["slug"]))
    return 0


def cmd_export(args):
    reg = load_registry(args.dir)
    c = find_char(reg, args.key)
    if not c:
        print("未找到人物: %s" % args.key)
        return 1
    src = os.path.join(args.dir, c["path"]) if not os.path.isabs(c["path"]) \
        else c["path"]
    if not os.path.isdir(src):
        print("人物包目录不存在: %s" % src)
        return 1
    out = args.zip_path
    if not out.endswith(".zip"):
        out += ".zip"
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(src):
            if "snapshots" in root or "__pycache__" in root:
                continue
            for fn in files:
                full = os.path.join(root, fn)
                rel = os.path.join(c["slug"],
                                   os.path.relpath(full, src))
                zf.write(full, rel)
    print("已导出: %s（%s，含全部记忆原文——zip 视为敏感数据）" % (out, c["name"]))
    return 0


def cmd_import(args):
    if not os.path.isfile(args.zip_path):
        print("zip 不存在: %s" % args.zip_path)
        return 1
    os.makedirs(chars_dir(args.dir), exist_ok=True)
    imported = []
    with zipfile.ZipFile(args.zip_path, "r") as zf:
        for info in zf.infolist():
            parts = info.filename.split("/")
            if len(parts) >= 2 and parts[0] not in ("", "__MACOSX") and \
                    parts[0] != parts[1]:
                # 顶层目录 = slug；防 zip-slip
                slug = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff_-]", "", parts[0])
                if not slug:
                    continue
                dest = os.path.join(chars_dir(args.dir), slug)
                target = os.path.normpath(os.path.join(dest,
                                                       *parts[1:]))
                if not target.startswith(os.path.normpath(dest) +
                                         os.sep) and target != dest:
                    print("跳过可疑路径: %s" % info.filename)
                    continue
                if info.is_dir():
                    os.makedirs(target, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with zf.open(info) as src_f, open(target, "wb") as dst_f:
                        shutil.copyfileobj(src_f, dst_f)
                imported.append(slug)
    slugs = sorted(set(imported))
    if not slugs:
        print("zip 中未发现人物包目录（顶层应为人物 slug）")
        return 1
    for slug in slugs:
        path = os.path.join(chars_dir(args.dir), slug)
        try:
            _s, name, tv, eras, standalone = probe_product_dir(path)
        except ValueError as e:
            print("跳过: %s" % e)
            continue
        reg = load_registry(args.dir)
        if not find_char(reg, slug):
            if not reg["characters"] or not reg["active"]:
                reg["active"] = slug
            reg["characters"].append({
                "name": name or slug, "slug": slug,
                "path": os.path.relpath(path, args.dir),
                "desc": "", "relation": "熟人",
                "template_version": tv, "eras": eras,
                "standalone": standalone,
                "registered": now(), "updated": now(),
            })
            save_registry(args.dir, reg)
        print("已导入: %s（slug=%s）" % (name or slug, slug))
    return 0


def cmd_remove(args):
    reg = load_registry(args.dir)
    c = find_char(reg, args.key)
    if not c:
        print("未找到人物: %s" % args.key)
        return 1
    reg["characters"] = [x for x in reg["characters"] if x["slug"] != c["slug"]]
    if reg["active"] == c["slug"]:
        reg["active"] = reg["characters"][-1]["slug"] if reg["characters"] else ""
    save_registry(args.dir, reg)
    print("已注销: %s" % c["name"])
    if args.delete:
        path = os.path.join(args.dir, c["path"]) if not os.path.isabs(
            c["path"]) else c["path"]
        if os.path.isdir(path):
            shutil.rmtree(path)
            print("  已删除人物包目录: %s" % path)
    else:
        print("  人物包文件保留（--delete 可连目录一起删）")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="溯洄 · 多人物注册表（v3）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="初始化平台目录（characters/ + registry.json）")
    p.add_argument("--dir", default=default_platform_dir())

    p = sub.add_parser("register", help="注册人物包（v1/v2 产物目录可直接注册）")
    p.add_argument("product", help="人物包目录")
    p.add_argument("--name", default="")
    p.add_argument("--desc", default="", help="一句话描述")
    p.add_argument("--relation", choices=RELATIONS, default="熟人",
                   help="与用户的关系（决定剧场第一句话的温度）")
    p.add_argument("--dir", default=default_platform_dir())
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("list", help="列出全部人物")
    p.add_argument("--dir", default=default_platform_dir())

    p = sub.add_parser("show", help="查看人物详情")
    p.add_argument("key", help="名字或 slug")
    p.add_argument("--dir", default=default_platform_dir())

    p = sub.add_parser("switch", help="设为当前人物")
    p.add_argument("key")
    p.add_argument("--dir", default=default_platform_dir())

    p = sub.add_parser("export", help="人物包导出 zip（迁移/分享，隐私用户控制）")
    p.add_argument("key")
    p.add_argument("zip_path")
    p.add_argument("--dir", default=default_platform_dir())

    p = sub.add_parser("import", help="导入人物包 zip")
    p.add_argument("zip_path")
    p.add_argument("--dir", default=default_platform_dir())

    p = sub.add_parser("remove", help="注销人物（--delete 连目录删除）")
    p.add_argument("key")
    p.add_argument("--delete", action="store_true")
    p.add_argument("--dir", default=default_platform_dir())

    args = ap.parse_args(argv)
    if args.cmd == "init":
        return cmd_init(args)
    if args.cmd == "register":
        return cmd_register(args)
    if args.cmd == "list":
        return cmd_list(args)
    if args.cmd == "show":
        return cmd_show(args)
    if args.cmd == "switch":
        return cmd_switch(args)
    if args.cmd == "export":
        return cmd_export(args)
    if args.cmd == "import":
        return cmd_import(args)
    if args.cmd == "remove":
        return cmd_remove(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
