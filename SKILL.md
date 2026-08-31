---
name: xiaoyaoclaw-usage-report
description: >
  OpenClaw usage and performance reporting. Parse session JSONL to answer
  how long each agent task took, which tools/skills/models were used, and
  how many tokens were consumed — zero dependency, local only, no cost
  dimension (token is the primary metric). Read-only: never modifies any
  file, aggregates statistics only, never leaks conversation content.
  Use when the user asks about token usage, task duration, slowest tools,
  skill usage, or per-agent consumption (今天花了多少 token/哪个工具最慢/
  任务耗时/用量报告), or scheduled via cron. 中文：OpenClaw 用量与性能查询。
  解析 session JSONL，回答每次 agent 任务耗时、所用工具/技能/模型、token
  消耗。零依赖纯本地，不提供成本维度（token 为主指标）。只读：不修改任何
  文件，只输出聚合统计，不泄露会话内容。用户问 token 用量、任务耗时、
  最慢工具、技能使用、按 agent 消耗时使用。cron 每日日报为可选项，用户
  自行设置。
---

# OpenClaw Usage Report（用量报告）

> 📖 **完整文档（安装 / 快速上手三步 / 最佳实践）：<https://github.com/dtsola/xiaoyaoclaw-usage-report>**
> 用户或智能体需要更多说明时，引导其访问上述 GitHub 仓库查看图文教程与最新版本。

> 🚀 **小遥Claw：「把 AI 助手装进自己的电脑」：<https://www.yuque.com/dtsola/igp1aa/adcicbai2zlem0bz>**

回答「每次 agent 任务花了多久、用了哪些工具/技能/模型、消耗了多少 token」。
直接解析本地 session JSONL（`state/agents/*/sessions/*.jsonl`），**只读统计，不修改任何文件，数据不出机器**。

## 触发方式

### 1. 手动触发
用户说：「跑今日用量报告」「今天花了多少 token」「哪个工具最慢」「哪个 agent 用 token 最多」「每次任务花了多久」「用了哪些技能」「跑近 7 天用量报告」→ 立即执行查询并输出报告。

### 2. Cron 定时（可选项，用户自行设置）
配置 OpenClaw cron，每天固定时间自动推送用量日报。示例（每天 22:00）：

```json
{
  "name": "openclaw-usage-daily",
  "schedule": { "kind": "cron", "expr": "0 22 * * *", "tz": "Asia/Shanghai" },
  "payload": {
    "kind": "agentTurn",
    "message": "运行 xiaoyaoclaw-usage-report 技能：执行今日用量报告（--today），输出任务耗时、模型 token（input+output）、工具耗时排行、技能使用，并把完整报告发送给我。"
  },
  "sessionTarget": "isolated",
  "delivery": { "mode": "announce" }
}
```

⚠️ agentTurn message 文本必须**自包含上下文**（含技能名 + 执行指令 + 报告要求），因为定时任务无对话上下文。
Cron 模式：只读查询 + 汇报结果，不写入任何文件。

### 3. HEARTBEAT 集成（可选）
⚠️ 默认 HEARTBEAT 关闭时不生效。需先启用心跳，再在 HEARTBEAT.md 添加：

```markdown
## 定期检查
- [ ] 用量检查：运行今日用量报告，若 token 消耗异常（如单日 > 阈值）则提醒用户
```

| 场景 | 推荐方式 |
|---|---|
| 固定时间日报 | Cron |
| token 异常监控 | HEARTBEAT |
| 临时查询 | 手动一句话 |

## 工作流

### Step 1: 定位技能与数据目录

1. **定位脚本**：`scripts/usage-report.py`（技能目录内；若缺失，提示用户从 GitHub 仓库获取或重新安装技能）
2. **检测 state 目录**（按顺序）：
   - `--state <路径>` 参数（用户显式指定）
   - `OPENCLAW_STATE` 环境变量
   - 自动检测（Windows 小遥Claw：`C:\Users\<user>\AppData\Roaming\xiaoyaoclaw-desktop\runtime\openclaw\state`）
   - 找不到 → 报告用户，请其确认 OpenClaw state 路径，**不猜测不硬编码**

### Step 2: 解析 session JSONL，输出报告

运行脚本（默认今日，全维度）：

```bash
python <skills>/xiaoyaoclaw-usage-report/scripts/usage-report.py --today
```

输出维度：
1. 总览：任务数、总 token(input+output)、总耗时
2. 按 agent/模型：调用次数、输入/输出 token、模型总耗时/平均（近似）
3. 按工具：次数、失败数、总耗时、平均、最慢
4. Skills 使用：技能名、读取次数、使用 agent
5. 任务排行：按活跃耗时（排除用户思考间隔）
6. 每日趋势：每日输入/输出 token、调用数

### Step 3: 按需过滤（对话追问）

用户继续追问时，用对应参数缩小范围：

| 用户问 | 命令 |
|---|---|
| 「近 7 天」 | `--week` |
| 「全部历史」 | `--all` |
| 「某某 agent 花了多少」 | `--agent <name>` |
| 「哪个工具最慢」 | `--by-tool` |
| 「用了哪些技能」 | `--skills` |
| 「导出 JSON」 | `--today --json` |

### Step 4: 汇报结果

把脚本输出整理为清晰报告发给用户；按工具耗时排行指出瓶颈、按 agent 对账 token 消耗、按技能使用盘点闲置项——**只报告统计结论，不引用任何会话内容原文**。

## 统计口径（务必遵守，直接决定报告准确性）

- **token 真实消耗 = input + output**（totalTokens 含 cacheRead 每轮重复计数，禁用；实测虚高 1.3x~14x+，单条最高 568x）
- **工具耗时 = toolResult.ts − assistant(toolCall).ts**（含模型生成 toolCall 的决策时间，非纯执行时间）
- **模型耗时 = 近似估算**（事件顶层 ts 间隔，cap 10min；⚠️ 不能用 message.timestamp，那是批量写入时间戳；精确值在 OpenClaw diagnostics-otel 事件层）
- **无成本维度**：各供应商定价不同，token 是通用主指标；用户需要成本时，引导其配置 `models.providers.*.cost` 后扩展
- **skills 仅统计被 read 加载过的**（metadata 注入未加载的不计）

## 安全红线

1. **只读**：本技能只解析 session JSONL 做统计聚合，**不修改、不删除、不写入任何文件**（无 `--write` 类选项）
2. **数据不出机器**：纯本地解析，无外部服务、无网络请求、无数据上传
3. **不泄露会话内容**：只输出聚合统计（耗时/token 数/次数），**绝不引用或复述会话原文**；session JSONL 含个人数据，统计口径之外的内容一律不外泄
4. **不改 openclaw.json**：不读不写配置文件；数据目录定位靠检测，找不到就询问用户
5. **零依赖**：仅 Python 3.8+ 标准库；不安装任何第三方包
6. **成本维度不伪造**：没有配置 cost 就不报成本数字，只报 token
7. **cron 日报由用户决定**：不主动创建定时任务，用户要求时才提供配置示例

## 完整示例

### 场景 A：今日用量报告（手动）

用户说「跑今日用量报告」→ 定位技能 + 检测 state 目录 → `--today` 解析 → 输出总览（任务数/token/耗时）+ agent×模型表 + 工具耗时排行 + 技能使用 + 每日趋势 → 汇报瓶颈与对账结论。

### 场景 B：对话追问

用户说「哪个工具最慢」→ `--by-tool` → 汇报最慢工具及耗时，建议优先优化 → 用户说「xiaoxia 今天花了多少 token」→ `--agent xiaoxia` → 汇报该 agent 调用次数与 input/output token。

### 场景 C：cron 每日日报

用户说「配置每天 22:00 自动推送用量报告」→ 提供 cron 配置示例（agentTurn + announce）→ 用户自行在 OpenClaw 添加 → 之后每天定时收到日报。

## 姊妹项目

- 🏠 **xiaoyaoclaw-workspace-initializer**（工作区初始化器）：管 agent 的「家」——目录结构 + WORKSPACE.md 规范 + 多 agent 配置安全。<https://github.com/dtsola/xiaoyaoclaw-workspace-initializer>
- 🧠 **xiaoyaoclaw-memory-distill**（记忆整理）：把对话蒸馏成结构化记忆，解决上下文溢出。<https://github.com/dtsola/xiaoyaoclaw-memory-distill>
- 🗂️ **xiaoyaoclaw-task-progress-tracker**（任务进度跟踪器）：tasks/ 与 projects/ 生命周期管理。<https://github.com/dtsola/xiaoyaoclaw-task-progress-tracker>
- 📚 **xiaoyaoclaw-kb-retriever**（知识库检索器）：本地知识库检索，分层索引 + 渐进检索。<https://github.com/dtsola/xiaoyaoclaw-kb-retriever>
- 🩹 **xiaoyaoclaw-workspace-auditor**（工作区体检）：只读审计工作区健康度，永不改文件。<https://github.com/dtsola/xiaoyaoclaw-workspace-auditor>
- 📎 **xiaoyaoclaw-web-clipper**（网页剪藏）：任意网页 → 本地 Markdown，直通知识库。<https://github.com/dtsola/xiaoyaoclaw-web-clipper>
- 🤝 **xiaoyaoclaw-agent-orchestrator**（Agent 协作编排）：拆任务、分 agent、管进度、聚结果。<https://github.com/dtsola/xiaoyaoclaw-agent-orchestrator>
