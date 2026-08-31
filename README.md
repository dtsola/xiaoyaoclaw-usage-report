<div align="center">

# OpenClaw Usage Report · 用量报告

**OpenClaw 用量与性能查询工具** — 回答「每次 agent 任务花了多久、用了哪些工具/技能/模型、消耗了多少 token」

零依赖 · 纯本地 · 数据不出机器

</div>

---

## 为什么需要它

OpenClaw 没有内置 per-task 性能面板，但本地 session JSONL（`state/agents/*/sessions/*.jsonl`）已完整记录每次任务/工具/模型调用的时间戳与 token 消耗。本工具直接消费这份数据，**无需任何额外采集、无外部依赖、无数据上传**。

适用于：优化应用前的用量基线分析、定位最慢工具、按 agent 对账 token 消耗、技能使用情况盘点。

## 能力

| 维度 | 说明 |
|------|------|
| 任务耗时 | 每次任务的窗口耗时 + 活跃耗时（排除用户思考间隔） |
| 模型 token | 按 agent/模型聚合：调用次数、输入/输出 token（真实消耗 = input+output） |
| 模型耗时 | 近似估算（事件 ts 间隔），按 agent/模型聚合总耗时与平均 |
| 工具耗时 | 按工具聚合：次数、失败数、总耗时、平均、最慢 —— 直接定位瓶颈 |
| Skills 使用 | 从 read 调用推断：技能名、读取次数、使用 agent |
| 每日趋势 | 每日输入/输出 token、调用数 |
| MCP 工具 | 与普通工具同构（toolCall/toolResult），天然覆盖 |

## 快速开始

```bash
# 今日报告（默认全维度）
python scripts/usage-report.py --today

# 近 7 天
python scripts/usage-report.py --week

# 全部历史
python scripts/usage-report.py --all

# 按 agent 过滤
python scripts/usage-report.py --agent xiaoxia

# 仅工具耗时明细 / 仅技能
python scripts/usage-report.py --by-tool
python scripts/usage-report.py --skills

# JSON 输出（可管道给其他工具 / 用于 cron 日报）
python scripts/usage-report.py --today --json > usage-report.json
```

数据目录默认自动检测（Windows 小遥Claw：`C:\Users\<user>\AppData\Roaming\xiaoyaoclaw-desktop\runtime\openclaw\state`）；可用 `--state <路径>` 或环境变量 `OPENCLAW_STATE` 覆盖。

### 示例输出

```
📊 总览: 7 个任务 | 总 token(input+output): 1,747,066 | 总耗时: 230.0m

📦 按 agent / 模型（token=input+output 真实消耗；模型耗时≈事件ts间隔，cap 10min）
  Agent     模型                      调用    输入tok    输出tok   模型总耗时  平均
  tiantong  deepseek/deepseek-v4-flash  146  1,513,943  150,870      28.3m  11.6s

🔧 按工具（耗时 = toolResult - toolCall）
  工具        次数  失败   总耗时   平均   最慢
  exec        204    1    54.5m  16.0s  6.2m
```

## 统计口径（重要）

1. **token 真实消耗 = input + output**。`totalTokens` 含 cacheRead（每轮重复计数），缓存命中率越高虚高越严重（实测 1.3x~14x+，单条最高 568x）——脚本已规避。
2. **工具耗时 = toolResult.ts − assistant(toolCall).ts**，含模型生成 toolCall 的决策时间（非纯执行时间）。
3. **模型耗时为近似估算**（assistant 事件 ts − 前一条事件 ts，cap 10min）。⚠️ 不能用 message.timestamp（批量写入时间戳）；精确 duration 仅在 OpenClaw diagnostics-otel 事件层。
4. **成本维度不提供**：各模型供应商定价不同，token 是通用主指标；如需成本，自行在 OpenClaw 配置 `models.providers.*.cost` 后扩展。
5. **skills 统计**：仅覆盖「被 read 加载过」的技能（metadata 注入未加载的不计）。

## Cron 每日日报（可选项，用户自行设置）

工具支持 `--today --json` 输出，可挂定时任务生成每日 token 日报。是否启用、何时推送，完全由使用者决定。

OpenClaw 内可用 cron：

```json
{
  "name": "openclaw-usage-daily",
  "schedule": { "kind": "cron", "expr": "0 22 * * *", "tz": "Asia/Shanghai" },
  "payload": {
    "kind": "agentTurn",
    "message": "运行 `python <脚本路径>/usage-report.py --today` 并把报告发送给我"
  },
  "sessionTarget": "isolated",
  "delivery": { "mode": "announce" }
}
```

或用 Windows 计划任务 / Linux crontab 直接跑脚本并输出到文件。

## 限制

- 任务「活跃耗时」为近似值（相邻事件间隔 <5min 累计），可能含 heartbeat/后台事件
- 仅支持 JSONL version 3 会话（历史早期格式不支持）
- 仅统计本机 OpenClaw 数据（多机需各自运行）

## 环境要求

- Python 3.8+（仅标准库，零依赖）
- 可读 OpenClaw state 目录（默认 `state/agents/*/sessions/*.jsonl`）

## 姊妹项目

- [xiaoyaoclaw-workspace-initializer](https://github.com/dtsola/xiaoyaoclaw-workspace-initializer)（家/规范）
- [xiaoyaoclaw-memory-distill](https://github.com/dtsola/xiaoyaoclaw-memory-distill)（内容/记忆）
- [xiaoyaoclaw-task-progress-tracker](https://github.com/dtsola/xiaoyaoclaw-task-progress-tracker)（状态/进度）
- [xiaoyaoclaw-kb-retriever](https://github.com/dtsola/xiaoyaoclaw-kb-retriever)（知识/检索）
- [xiaoyaoclaw-workspace-auditor](https://github.com/dtsola/xiaoyaoclaw-workspace-auditor)（健康/体检）
- [xiaoyaoclaw-web-clipper](https://github.com/dtsola/xiaoyaoclaw-web-clipper)（输入/剪藏）
- [xiaoyaoclaw-agent-orchestrator](https://github.com/dtsola/xiaoyaoclaw-agent-orchestrator)（协作/编排）

## License

MIT © dtsola
