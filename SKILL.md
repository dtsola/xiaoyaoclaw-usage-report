---
name: xiaoyaoclaw-usage-report
description: >
  OpenClaw usage and performance reporting. Parse session JSONL to answer
  how long each agent task took, which tools/skills/models were used, and
  how many tokens were consumed — zero dependency, local only, no cost
  dimension (token is the primary metric). Use when the user asks about
  token usage, task duration, slowest tools, skill usage, or per-agent
  consumption (今天花了多少 token/哪个工具最慢/任务耗时/用量报告).
  中文：OpenClaw 用量与性能查询。解析 session JSONL，回答每次 agent
  任务耗时、所用工具/技能/模型、token 消耗。零依赖纯本地，不提供成本
  维度（token 为主指标）。用户问 token 用量、任务耗时、最慢工具、
  技能使用、按 agent 消耗时使用。cron 每日日报为可选项，用户自行设置。
---

# OpenClaw Usage Report

OpenClaw 用量与性能查询工具：读取本地 session JSONL（`state/agents/*/sessions/*.jsonl`），
输出任务耗时、工具耗时、模型 token/耗时、skills 使用、每日趋势。

零依赖（纯 Python 标准库）、纯本地、无外部服务、无成本维度（token 为主指标）。

## 触发场景

- 「今天花了多少 token」「哪个工具最慢」「哪个 agent 用 token 最多」
- 「每次任务花了多久」「用了哪些技能」
- 优化应用前的用量基线分析

## 用法

```bash
python <skills>/xiaoyaoclaw-usage-report/scripts/usage-report.py --today    # 今日（默认全维度）
python <skills>/xiaoyaoclaw-usage-report/scripts/usage-report.py --week     # 近 7 天
python <skills>/xiaoyaoclaw-usage-report/scripts/usage-report.py --all      # 全部
python <skills>/xiaoyaoclaw-usage-report/scripts/usage-report.py --agent <name>   # 按 agent 过滤
python <skills>/xiaoyaoclaw-usage-report/scripts/usage-report.py --by-tool  # 仅工具耗时
python <skills>/xiaoyaoclaw-usage-report/scripts/usage-report.py --skills   # 仅技能使用
python <skills>/xiaoyaoclaw-usage-report/scripts/usage-report.py --today --json   # JSON 输出
```

数据目录自动检测（Windows 小遥Claw：`C:\Users\<user>\AppData\Roaming\xiaoyaoclaw-desktop\runtime\openclaw\state`）；覆盖用 `--state <路径>` 或环境变量 `OPENCLAW_STATE`。

## 输出维度

1. 总览：任务数、总 token(input+output)、总耗时
2. 按 agent/模型：调用次数、输入/输出 token、模型总耗时/平均（近似）
3. 按工具：次数、失败数、总耗时、平均、最慢
4. Skills 使用：技能名、读取次数、使用 agent
5. 任务排行：按活跃耗时（排除用户思考间隔）
6. 每日趋势：每日输入/输出 token、调用数

## 统计口径（务必遵守）

- **token 真实消耗 = input + output**（totalTokens 含 cacheRead 会重复计数，禁用；实测虚高 1.3x~14x+）
- **工具耗时 = toolResult.ts − assistant(toolCall).ts**（含模型决策时间）
- **模型耗时 = 近似估算**（事件顶层 ts 间隔，cap 10min；⚠️ 不能用 message.timestamp，那是批量写入时间戳；精确值在 diagnostics-otel 事件层）
- **无成本维度**：各供应商定价不同，token 是通用主指标
- **skills 仅统计被 read 加载过的**（metadata 注入不计）

## Cron 每日日报（可选项，用户自行设置）

工具支持 `--today --json`，可挂定时任务生成日报。是否启用由使用者决定：

- OpenClaw cron：`agentTurn` 跑脚本 + `delivery.announce` 推送（示例见 README.md）
- 或 Windows 计划任务 / Linux crontab 直接执行脚本输出到文件

## 限制

- 活跃耗时为近似值（间隔 <5min 累计，可能含 heartbeat）
- 仅支持 JSONL version 3 会话
- 仅统计本机数据

## 环境要求

- Python 3.8+（标准库，零依赖）
- 可读 OpenClaw state 目录

## 姊妹项目

与 xiaoyaoclaw-workspace-initializer（家/规范）、xiaoyaoclaw-memory-distill（内容/记忆）、
xiaoyaoclaw-task-progress-tracker（状态/进度）、xiaoyaoclaw-kb-retriever（知识/检索）、
xiaoyaoclaw-workspace-auditor（健康/体检）、xiaoyaoclaw-web-clipper（输入/剪藏）、
xiaoyaoclaw-agent-orchestrator（协作/编排）组成小遥生态工具链。
