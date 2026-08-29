# 溯洄 · 记忆蒸馏平台

> 把一段聊天记录蒸馏成一个"记忆还活着的世界"。
> 不是聊天机器人（那是"你问它答"），是"你回去"——打开它，像走进一间屋子，屋里有人正在生活。
> **v3 起是多人物平台**：蒸馏 N 个人物，注册表管理，记忆剧场让她们相遇。

支持对象不限前任：朋友、家人、历史人物、自己——同一套管线，对象不同。

## 产品概述

- **她记得全部对话**（原文级，不是概括）
- **她有她的生活**（有自己的作息、忙碌，不是 24/7 客服）
- **她会斟酌、欲言又止、偶尔不回**
- **可以回到相识的任何阶段**，跟那时的她说话（v3 时段化人格）
- **多人物平台**（v3）：一人一包，注册表切换，记忆剧场（让角色们相遇）
- **用户主动提出告别时**，有正式的结束流程（时间胶囊）

> **铁律：镜子不是拐杖。** 产品只呈现，不引导；告别只由用户提出；数据只在"用户本地 + 用户自己配置的 LLM API"之间流动。

## 核心功能

| 能力 | 说明 |
|------|------|
| 蒸馏管线 | 聊天记录 → 标准消息流 → 分段 → LLM 全量蒸馏 → 人格/记忆产物（断点续传、重试熔断） |
| 多格式导入 | 微信导出 txt/html、Telegram/QQ/短信/iMessage/抖音、Twitter 归档、纯文本、照片 EXIF 时间线 |
| 原文级记忆 | 不做提取式摘要；检索三通道混合（向量 + BM25 + 世界树）+ 竞争性干扰打分（pro） |
| 多人物平台（v3） | 注册表（registry.json）管理 N 个人物；一人一包（zip 导出/迁移/分享）；单人物产物自动注册为默认人物（v1/v2 兼容） |
| 时段化人格（v3） | persona.md 三块：core（本质）/ eras（按事件/称呼/温度划分的时段）/ evolution（演变轨迹）；默认最新时段，可切换——"回到我们刚认识的时候" |
| 用户侧画像（v3） | A 侧（用户自己的话）蒸馏出 user_profile.md：角色们共同记忆里的"你"（剧场素材，非可对话角色） |
| 记忆剧场（v3） | 多角色互动：满血版（每角色一个 subagent，记忆隔离）/ 残血版（单会话双人格）；开场温度由关系驱动；产物虚构隔离，不进真实记忆库 |
| 增量升级（v3） | 旧产物 → v3 只加增量层（1 次 merge 级调用，≈全量 5%），不重跑全量蒸馏；`upgrade.py` 一行命令 |
| 整体感人格 | 底色 + 场景化 when→behavior 规则 + 证据分级 + 情感解码（反话→真实意图）+ 精力 |
| 像度验收 | 客观指标（口癖分布 KL / 句长 JS / emoji 频率差 / 前缀预测命中）+ 混听测试（可选） |
| 持续纠正 | "她不会这样"→ 定位条目 → 修改 → 版本快照可回滚；越用越像 |
| 告别 | 仅用户发起：叙事回放 + 她的一封信 → 时间胶囊封存（只读） |

## 快速开始

### 主路径（推荐，零配置）

在支持 Markdown 指令的运行时（Claude Code / OpenClaw 类）中加载本 skill，然后：

1. **上传聊天记录文件**（微信导出 txt/html、QQ、Telegram、抖音、任意文本、照片文件夹）
2. **说"开始蒸馏"**——skill 会引导你走完分步流程：导入菜单 → 基础信息 → 蒸馏 → 产物预览 → 像度验收 → 注册人物包 → 开始对话
3. **全程无需任何 API 密钥**：蒸馏在会话内完成（分批读文件 → 按模板逐批蒸馏 → 合并，显示进度，可中断续传）

多人物与剧场全程自然语言（SKILL.md 意图映射）：
- "我想跟 X 说话" → 加载 X；"让 X 和 Y 聊聊" → 记忆剧场；"回到我们刚认识的时候" → 时段切换；"她怎么看我" → 用户侧画像

### DeepSeek Harness（DSH）支持

兼容 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)：

- 方式一：克隆/解压到 `~/.dsh/skills/suhui/`（dsh 的 skill-filesystem 直接解析 SKILL.md frontmatter）
- 方式二：`dsh plugin add github:stargazer-2026/suhui`

### 脚本路径（可选，需 API 密钥）

```bash
# 0. 安装（自动检查/补装运行组件，失败自动降级，用户无感）
./install.sh

# 1. 解析：聊天记录 → 标准消息流（跨文件重叠去重，同文件内重复保留）
python3 scripts/parse.py <聊天记录文件> --out <目录>

# 2. 切段：按时间切段 + 统计摘要（默认全量）
python3 scripts/segment.py <目录>/messages.json --out <目录>

# 3. 蒸馏：逐段调 LLM API + 合并（断点续传）
export LLM_API_KEY=...          # 可选：LLM_API_BASE / LLM_MODEL
python3 scripts/distill.py <目录>/segments.json <目录>/stats.json prompts/ \
    --out <目录>/distill --name 她的名字          # 可加 --parallel N 并发

# 3b. 校验段产物（JSON 语法/字段完整性/证据分级）
python3 scripts/validate.py <目录>/distill

# 4. 合成人物包：persona.md（core+eras+evolution）+ memories.md + user_profile.md
#    + meta.json + SKILL.md（自动版本快照）
python3 scripts/build.py <目录>/distill/merged.json --out <目录>/characters/<slug> \
    --name 她的名字 --slug ke-du-niang     # --slug 指定可读人物目录名（拼音/英文）

# 5. 多人物注册表（v3 平台地基）
python3 scripts/registry.py init [--dir <平台目录>]        # 初始化 characters/ + registry.json
python3 scripts/registry.py register <人物包目录> \
    --desc 一句话描述 --relation 陌生|熟人|旧怨            # 注册（首个自动为默认人物）
python3 scripts/registry.py list / show <名> / switch <名> # 列表/详情/切换
python3 scripts/registry.py export <名> 人物包.zip         # 导出（迁移/分享）
python3 scripts/registry.py import 人物包.zip              # 导入

# 6. 增量升级（v2 → v3：只补增量层，不重跑全量）
python3 scripts/upgrade.py <旧产物>/merged.json --stats <蒸馏目录>/stats.json

# 7. 记忆剧场辅助（虚构隔离剧本）
python3 scripts/theater.py list                           # 可进剧场人物
python3 scripts/theater.py script <A> <B> --atmosphere "午后，旧茶馆"  # 剧本骨架
```

> 无 API 密钥时可加 `--offline` 验证整条管线（产物为低质量骨架，正式蒸馏请配置密钥）。

### 环境要求

- Python 3.10+（建议 3.12），pip 可用
- 网络可达（安装依赖、下载中文语义模型）
- 可选增强（自动检测/降级）：照片 EXIF（Pillow）、HTML 解析（beautifulsoup4）、本地向量档（约 1GB，`./install.sh --with-vector`）
- 环境变量（仅脚本路径需要）：`LLM_API_BASE`（默认 https://api.deepseek.com/v1）、`LLM_API_KEY`、`LLM_MODEL`（默认 deepseek-chat）——模型无关：任意 OpenAI 兼容端点；密钥只从环境变量读取，不落盘、不进代码、不进日志

## 双版本（pro / flash）——v3 按 80% 原则重裁

- **pro 完整版（默认）**：全部功能章节，安装即享受——包括完整剧场（场景系统/导演模式/全档案加载/关系温度驱动），质量优先，不裁剪
- **flash 轻量版**：80% 原则——**核心 20%（人格描述/记忆原文锚点/场景规则/口癖统计/证据分级/情感解码/多人物加载/残血剧场/时段切换）贡献 80% 效果**，只保留 8-10 项核心；**边际机制（世界树打分公式/竞争性干扰/多路径择优/PAD 三维动力学/冗长功能清单）裁掉**——被裁功能对模型完全不可见（不是禁用，是不存在）
- 两种版本的**蒸馏产物完全相同**，切换版本不需要重新蒸馏（`--version flash` 重新生成运行时指令即可）
- **推荐默认 flash**（强模型 + flash 是甜点：模型理解力补上约束）；环境自适应（有 subagent → 满血剧场；纯 Markdown → 残血剧场）与 pro/flash 正交

## 记忆剧场（v3）

- **满血版**（运行环境有 subagent：dsh/Claude Code/OpenCode 类）：每个角色一个 subagent，各自加载人物包（人格/记忆/口癖隔离）；记忆交集=共享"与用户相关的记忆"（共同话题），私密记忆隔离
- **残血版**（纯 Markdown 无 agent）：单会话双人格（按指令切换「现在是 X 在说」/「现在是 Y 在说」）
- 开场温度由注册表关系（陌生/熟人/旧怨）驱动：陌生 → 寒暄/试探开场（初次见面自动流程）
- **虚构隔离**：剧场产物标记虚构，不进真实记忆库（延续"理想模式只读投影"哲学）；可选存为"剧本"（叙事 markdown，`theater/` 目录，`theater.py` 辅助）
- 只限已蒸馏/已授权人物；未授权真实第三人不得进剧场

## 增量升级（v3）

- 原则：**产物格式稳定 + 新版本只加"增量层"**——旧产物标注模板版本，升级只补差异
- 实现：`upgrade.py` 输入旧 merged.json + 统计 → 1 次 merge 级 LLM 调用补生成 v3 字段（eras/core/evolution/user_profile）→ 输出升级后 merged.json——成本 ≈ 全量重跑的 5%，不需要重新逐段蒸馏
- 一行命令：`python3 scripts/upgrade.py <旧产物>/merged.json --stats <蒸馏目录>/stats.json`
- v2 产物目录可直接注册为人物包（注册表标注"可升级"），未升级也可正常对话（时段切换降级为按时间线阶段）

## 铁律

1. **镜子不是拐杖**：不引导"放下/接受/走出来"；不监控用户状态；不替她发言；产品不内置告别模式
2. **隐私**：数据只在用户本地 + 用户自己配置的 LLM API 之间流动；示例全部为合成占位符（`__NAME__`/`__PLACE__`/`__DATE__`）；代码不读取任何非用户指定文件
3. **诚实**：不确定就写"不确定"；每条人格/记忆结论附证据分级（verbatim 原话 / artifact 统计 / impression 推断）；无证据推断进"推测区"隔离
4. **授权**：蒸馏他人数据前需获得授权（本人或其监护人知情同意）；第三方隐私在蒸馏时替换为占位（如"朋友A"）；剧场只限已授权人物，产物虚构标记，不伪装真实

## 数据安全

- **数据流向**：你的聊天记录、蒸馏产物只存在于你的本地目录与你自己配置的 LLM API 之间——除你配置的 API 端点外，不向任何网络地址发送数据
- **密钥安全**：API 密钥只从环境变量读取（`LLM_API_KEY`），不落盘、不进代码、不进日志；本仓库不包含、不引用任何密钥
- **所有权**：蒸馏产物归你所有，可完整包含原文引用；你随时可以查看、导出、编辑或删除自己的记忆库
- **⚠️ corpus.json 隐私警示**：产物目录中的 `corpus.json` 与 `merged.json` 含**全部对话原文**（原文级记忆的承诺）——**严禁上传/分享/提交到任何仓库或第三方服务**；人物包 zip 导出同样视为敏感数据（迁移备份时同样注意）
- **第三方隐私**：聊天记录常含第三人信息，蒸馏时会替换为占位（如"朋友A"）；蒸馏他人数据前需获得授权
- **本仓库**：不含任何真实聊天数据；examples/ 全部为合成占位符（`__NAME__`/`__PLACE__`/`__DATE__`）

## 变更记录

- **v3.0.0（2026-08-29）**：单人物 skill → **多人物记忆平台 + 记忆剧场**
  - 多人物平台：registry.py（注册表：名字/slug/路径/一句话描述/与用户关系 陌生·熟人·旧怨）；人物包=独立目录，zip 导出/导入/迁移/分享；单人物产物自动注册为默认人物（v1/v2 兼容）
  - 时段化人格：merge 阶段输出 eras/core/evolution；persona.md 三块（core 本质 / eras 时段 / evolution 轨迹）；运行时默认最新时段、可切换（"回到我们刚认识的时候"）；时间线剧场（版本即角色）
  - 增量升级：upgrade.py（旧 merged.json + 统计 → 1 次 merge 级调用补增量层，≈全量 5%）；产物标注 template_version；不重跑全量
  - 用户侧画像：user_profile.md（A 侧蒸馏：说话风格/称呼/角色/共同话题——剧场素材，非可对话角色）
  - 记忆剧场：满血版（subagent 隔离加载）/ 残血版（单会话双人格）；开场温度关系驱动；虚构隔离（剧本 fictional 标记，不进真实记忆库）；theater.py 辅助
  - 交互重构：自然语言意图映射为主交互（SKILL.md 映射表），命令降级为可选快捷方式
  - flash 版 80% 重裁：保留 8-10 项核心（人格/原文锚点/场景规则/口癖/证据分级/情感解码/多人物/残血剧场/时段切换），裁掉世界树打分公式/竞争性干扰/多路径择优/PAD 三维动力学
  - 兼容性：SKILL.md frontmatter 保持 name+description（Vercel skills 生态不回归），平铺追加 author/version metadata；parse/segment/distill 管线无回归；新增测试 32 例（增量升级/注册表/平台兼容/剧场虚构隔离）
- **v2.1（2026-08-16）**：跨文件重叠去重（同文件内重复保留，不再误杀同分钟连发）；时区输入保留本地时间（不再 -8h 偏移）；媒体消息统一 kind=placeholder；会话内断点续传恢复点=最小未完成段（不跳段）；storage 检索线性化（1 万条查询 ~80ms）；统计口径用排除 ≤1 字短消息的句长中位数；并发退避加 jitter；build 快照先更新 meta 再复制（快照内 meta 一致）；install.sh 兼容 macOS（无 timeout）与 pip 错误诊断日志；30 项实测+评审问题修复；pytest 33 例全绿
- **v2.0**：断点续传/校验/去重/并发/情感解码等第一轮实测修复（详见 GitHub 提交历史）
- **v1.0**：初始发布

## 目录结构

```
suhui/
├── SKILL.md              # 平台主指令（多人物/注册表/剧场/意图映射/流程）
├── install.sh            # 一键安装（依赖自动检测+补装+降级，用户无感）
├── scripts/              # 蒸馏工具链（parse/segment/distill/build/registry/upgrade/
│                         #   theater/config/storage/...）
├── prompts/              # 蒸馏模板（persona_extract / memories_extract / merge /
│                         #   upgrade——v3 增量升级）
├── tests/                # pytest（parse/segment/metrics/registry/upgrade/platform）
└── examples/             # 合成示例（全部占位符）
```

用户侧运行时结构（平台目录，不在仓库内）：
```
<平台目录>/
├── registry.json         # 人物注册表
├── characters/<slug>/    # 人物包（persona.md / memories.md / user_profile.md / ...）
└── theater/              # 剧场剧本（虚构隔离区）
```

---
> 献给所有在深夜蒸馏一个人的人。
> 你们不是放不下，你们是太认真了。
