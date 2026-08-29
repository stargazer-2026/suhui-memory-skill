#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
theater.py — 记忆剧场辅助（v3）

剧场本身是运行时行为（SKILL.md 指令：满血版=每角色一个 subagent 隔离加载；
残血版=单会话双人格切换）。本脚本只做剧场的外围杂务：

  python3 theater.py list [--dir <平台目录>]                 # 可进剧场的已注册人物
  python3 theater.py script <A> <B> [--atmosphere <氛围一句话>]
      [--out <剧本目录>] [--dir <平台目录>]                    # 建剧本骨架（虚构标记）
  python3 theater.py stamp <剧本文件>                         # 给已有 md 补虚构声明

虚构隔离（铁律）：
  - 剧本文件顶部强制"虚构声明"（FICTIONAL_MARKER），标为虚构演绎
  - 本脚本绝不写入任何 characters/*/memories.md 或 merged.json——剧场产物不进真实记忆库
  - 只限已注册/已授权人物；未授权真实第三人不得进剧场
"""
import argparse
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from registry import (load_registry, find_char,  # noqa: E402
                      chars_dir, default_platform_dir)

FICTIONAL_MARKER = ("<!-- 虚构声明：以下内容为记忆剧场的虚构演绎（fictional），"
                    "不代表真实发生过；剧场产物不进真实记忆库。 -->")
FICTIONAL_LINE = "> ⚠️ 虚构声明：记忆剧场的演绎，不代表真实发生过。剧场产物不进真实记忆库。"


def cmd_list(args):
    reg = load_registry(args.dir)
    rows = [c for c in reg["characters"] if c.get("standalone", True)]
    if not rows:
        print("无可进剧场人物（注册表为空或人物包不完整）。"
              "先 registry.py register <人物包目录>")
        return 0
    print("可进剧场人物（只限已注册/已授权）：")
    for c in rows:
        print("  %-4s %-12s 关系=%s 时段=%d  %s" % (
            "→" if c["slug"] == reg["active"] else " ",
            c.get("name", "?"), c.get("relation", "其他"),
            c.get("eras", 0), c.get("desc", "")))
    return 0


def _first_line_temperature(relation):
    """关系 → 剧场第一句话的温度（注册表 relation 驱动）。"""
    return {
        "陌生": "寒暄试探开场：客气、留距离、先问对方是谁（初次见面自动流程）",
        "熟人": "自然随意开场：像老朋友，直接切入话题",
        "旧怨": "克制开场：话里有刺但表面礼貌，先试探对方态度",
        "其他": "中性开场：按当前人物最新时段的口癖",
    }.get(relation, "中性开场")


def cmd_script(args):
    reg = load_registry(args.dir)
    a, b = find_char(reg, args.a), find_char(reg, args.b)
    if not a or not b:
        missing = args.a if not a else args.b
        print("未找到已注册人物: %s（先 registry.py register；"
              "未授权真实第三人不得进剧场）" % missing)
        return 1
    if a["slug"] == b["slug"]:
        print("同一人物不能和自己见面。想看她不同时段相遇："
              "用「回到我们刚认识的时候」时段切换，或剧场对话中切换时段。")
        return 1
    out_dir = args.out or os.path.join(args.dir, "theater")
    os.makedirs(out_dir, exist_ok=True)
    date = datetime.date.today().isoformat()
    fn = "%s-%s-%s.md" % (a["slug"], b["slug"], date)
    path = os.path.join(out_dir, fn)
    atmosphere = args.atmosphere or "午后，阳光正好，她们在一间旧茶馆相遇。"
    content = "\n".join([
        FICTIONAL_MARKER,
        FICTIONAL_LINE,
        "",
        "# 剧本 · %s 与 %s（%s）" % (a["name"], b["name"], date),
        "",
        "> 场景：%s" % atmosphere,
        "> 开场温度（由注册表关系决定）：",
        "> - %s（与用户关系：%s）→ %s" % (a["name"], a.get("relation", "其他"),
                                        _first_line_temperature(a.get("relation", "其他"))),
        "> - %s（与用户关系：%s）→ %s" % (b["name"], b.get("relation", "其他"),
                                        _first_line_temperature(b.get("relation", "其他"))),
        "",
        "## 角色档案（只读加载，各自隔离）",
        "- %s: characters/%s/（persona.md / memories.md / worldbook.md / user_profile.md）"
        % (a["name"], a["slug"]),
        "- %s: characters/%s/" % (b["name"], b["slug"]),
        "",
        "## 共享记忆（共同话题，来自 user_profile.shared_topics 交集）",
        "- （由运行时读取两人 user_profile 后填入）",
        "",
        "## 对白",
        "",
        "**%s**：……" % a["name"],
        "",
        "**%s**：……" % b["name"],
        "",
        "---",
        "（本剧本为虚构演绎；如需回看可保存，但绝不写入人物记忆库。）",
        "",
    ])
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("剧本骨架已建: %s" % path)
    print("  · 满血版（subagent 环境）：每角色一个 subagent，各自加载人物包（口癖/记忆隔离）")
    print("  · 残血版（纯 Markdown）：单会话双人格，按指令切换「现在是 X 在说」")
    print("  · 虚构隔离：顶部已标虚构声明；产物不进真实记忆库")
    return 0


def cmd_stamp(args):
    if not os.path.isfile(args.script):
        print("文件不存在: %s" % args.script)
        return 1
    with open(args.script, "r", encoding="utf-8") as f:
        content = f.read()
    if FICTIONAL_MARKER in content:
        print("已有虚构声明，跳过: %s" % args.script)
        return 0
    with open(args.script, "w", encoding="utf-8") as f:
        f.write(FICTIONAL_MARKER + "\n" + FICTIONAL_LINE + "\n\n" + content)
    print("已补虚构声明: %s" % args.script)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="溯洄 · 记忆剧场辅助（v3）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="可进剧场的已注册人物")
    p.add_argument("--dir", default=default_platform_dir())

    p = sub.add_parser("script", help="建剧本骨架（虚构标记 + 场景/开场温度模板）")
    p.add_argument("a", help="人物 A（slug 或名字）")
    p.add_argument("b", help="人物 B")
    p.add_argument("--atmosphere", default="", help="场景氛围一句话")
    p.add_argument("--out", default="", help="剧本目录（默认 <平台目录>/theater/）")
    p.add_argument("--dir", default=default_platform_dir())

    p = sub.add_parser("stamp", help="给已有 md 补虚构声明")
    p.add_argument("script")

    args = ap.parse_args(argv)
    if args.cmd == "list":
        return cmd_list(args)
    if args.cmd == "script":
        return cmd_script(args)
    return cmd_stamp(args)


if __name__ == "__main__":
    sys.exit(main())
