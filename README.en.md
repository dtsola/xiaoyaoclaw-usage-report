# OpenClaw Usage Report 📊

> Usage & performance reporting for OpenClaw — how long each task took, which tools/skills/models were used, how many tokens were consumed.

<p align="center">
  <img src="./assets/readme/hero.svg" width="100%" alt="OpenClaw Usage Report — parse session JSONL for task duration, tool/skill/model usage and token consumption, zero-dependency & local-only">
</p>

> Answer "how long did each agent task take, which tools/skills/models were used, how many tokens were consumed".
> OpenClaw usage & performance reporting — parse session JSONL locally, zero dependency, data never leaves your machine.

![license](https://img.shields.io/badge/license-MIT-green)
[![ClawHub downloads](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fclawhub.ai%2Fapi%2Fv1%2Fskills%2Fxiaoyaoclaw-usage-report&query=skill.stats.downloads&label=ClawHub%20downloads&color=blue)](https://clawhub.ai/dtsola/skills/xiaoyaoclaw-usage-report)

## Why you need it

OpenClaw has no built-in per-task performance panel. Trying to optimize your agents, you:
- ❌ **Don't know how long each task took** — no timing stats, just gut feeling
- ❌ **Can't find the slowest tool** — is exec / web_fetch / process the bottleneck? No data
- ❌ **Can't reconcile token usage** — how many tokens per agent/model? All blurry
- ❌ **No trace of skill usage** — which skills were used, how many times? Nobody knows

But the data has always been there — local session JSONL files (`state/agents/*/sessions/*.jsonl`) already record timestamps and token usage for every task, tool call, and model call. This tool consumes that data directly: **zero dependency · local only · data never leaves your machine**.

## Features

- ⏱️ **Task duration** — wall-clock + active duration per task (excludes user thinking gaps)
- 🔢 **Model tokens** — per agent/model: call count, input/output tokens (real usage = input+output)
- 🧮 **Model latency** — estimated (event-ts gap, capped at 10 min), total & average per agent/model
- 🔧 **Tool latency** — per tool: count, errors, total/avg/max duration — find bottlenecks at a glance
- 🧩 **Skill usage** — inferred from `read` calls: skill name, load count, agents
- 📈 **Daily trend** — daily input/output tokens and call counts
- 🤖 **MCP tools** — same structure as regular tools (toolCall/toolResult), covered natively
- 🔒 **Zero-dependency, local-only** — pure Python standard library, no uploads
- ⏰ **Optional Cron daily report** — `--today --json` for scheduled reports; enable it yourself

## Install

```bash
# From ClawHub (recommended)
clawhub install xiaoyaoclaw-usage-report

# Or manually from GitHub
git clone https://github.com/dtsola/xiaoyaoclaw-usage-report
# Put scripts/usage-report.py into your scripts directory
```

## Usage

1. Install the skill (from ClawHub, or drop it into your skills directory manually)
2. Just tell your agent "**run today's usage report**" — it will automatically:
   - Locate the usage-report skill → detect the OpenClaw state directory
   - Parse all agents' session JSONL → output task duration / model tokens / tool latency / skill usage / daily trend
3. Keep asking conversationally: slowest tool, per-agent accounting, 7-day trend, skill inventory
4. Optional: say "schedule a usage report push at 22:00 daily" for an automatic daily report

### CLI reference (optional)

Prefer running the script directly instead of chatting:

```bash
python scripts/usage-report.py --today    # today (all dimensions by default)
python scripts/usage-report.py --week     # last 7 days
python scripts/usage-report.py --all      # all history
python scripts/usage-report.py --agent xiaoxia   # filter by agent
python scripts/usage-report.py --by-tool  # tool latency only
python scripts/usage-report.py --skills   # skills only
python scripts/usage-report.py --today --json > usage-report.json   # JSON output
```

The data directory is auto-detected (Windows XiaoyaoClaw: `C:\Users\<user>\AppData\Roaming\xiaoyaoclaw-desktop\runtime\openclaw\state`); override with `--state <path>` or the `OPENCLAW_STATE` env var.

## 🚀 Quick Start (3 steps, 5 minutes)

### Step 1: Install the skill

```bash
clawhub install xiaoyaoclaw-usage-report
```

### Step 2: Trigger your first report with one sentence

Tell your agent:

> Run today's usage report

The agent automatically: locates the usage-report skill → detects the state directory → parses all session JSONL → outputs task duration / model tokens / tool latency / skill usage / daily trend overview.

### Step 3: Verify + conversational follow-ups

Check these key blocks in the report:

```
📊 总览: 7 个任务 | 总 token(input+output): 1,747,066 | 总耗时: 230.0m

📦 按 agent / 模型（token=input+output 真实消耗；模型耗时≈事件ts间隔，cap 10min）
  Agent     模型                      调用    输入tok    输出tok   模型总耗时  平均
  tiantong  deepseek/deepseek-v4-flash  146  1,513,943  150,870      28.3m  11.6s

🔧 按工具（耗时 = toolResult - toolCall）
  工具        次数  失败   总耗时   平均   最慢
  exec        204    1    54.5m  16.0s  6.2m
```

No need to memorize any commands — just ask:

> Which tool is the slowest? Which agent consumed the most tokens? What's the daily trend over the last 7 days?

Want a daily report pushed automatically? Tell your agent:

> Schedule a usage report push at 22:00 daily

### Daily habits

| Scenario | Tell your agent |
|---|---|
| Daily reconciliation | "Run today's usage report", or schedule a 22:00 Cron push |
| Find bottlenecks | "Which tool is the slowest" → optimize it first |
| Skill inventory | "Which skills are used a lot, which are idle" |
| Per-agent accounting | "How many tokens did xiaoxia use today" |
| Pre-release review | "Run the last 7 days usage report" for the trend |
| Automation | "Schedule a usage report push at 22:00 daily" |

## Statistics rules (important)

1. **Real token usage = input + output**. `totalTokens` includes cacheRead (re-counted every turn; measured inflation 1.3x–14x+, up to 568x per message) — the script already avoids this.
2. **Tool duration = toolResult.ts − assistant(toolCall).ts**, includes the model's tool-call decision time (not pure execution time).
3. **Model latency is an estimate** (assistant event ts − previous event ts, capped at 10 min). ⚠️ Do not use `message.timestamp` (batch-write timestamp); exact duration lives only in the diagnostics-otel event layer.
4. **No cost dimension**: pricing differs per provider; tokens are the universal metric. To add costs, configure `models.providers.*.cost` in OpenClaw and extend.
5. **Skill stats** cover only skills actually loaded via `read` (metadata-injected but never loaded ones are not counted).

## Cron daily report (optional, user-configured)

The tool supports `--today --json` output for scheduled daily token reports. Whether to enable it and when to push is entirely up to the user.

OpenClaw cron example:

```json
{
  "name": "openclaw-usage-daily",
  "schedule": { "kind": "cron", "expr": "0 22 * * *", "tz": "Asia/Shanghai" },
  "payload": {
    "kind": "agentTurn",
    "message": "Run `python <script-path>/usage-report.py --today` and send me the report"
  },
  "sessionTarget": "isolated",
  "delivery": { "mode": "announce" }
}
```

Or use Windows Task Scheduler / Linux crontab to run the script directly.

## How it compares

| | claw-lens (local dashboard) | **xiaoyaoclaw-usage-report** |
|---|---|---|
| Form | Node web dashboard, needs a running service | ✅ Zero-dependency Python CLI, single file |
| Install cost | npm install + always-on service | ✅ Copy & run |
| Data source | Same session JSONL | ✅ Same session JSONL |
| Model latency | Not provided | ✅ Estimated (event-ts gap) |
| Token accounting | Not distinguished | ✅ Real usage input+output, avoids cacheRead inflation |
| Output | Web visualizations | ✅ Terminal tables + JSON pipeline (cron/CI friendly) |
| Data safety | Local | ✅ Local, zero upload |

## Directory structure

```
xiaoyaoclaw-usage-report/
├── SKILL.md                    # the skill itself (usage + triggers)
├── scripts/
│   └── usage-report.py         # main script (zero-dependency stdlib)
├── docs/
│   └── DESIGN.md               # design document
├── assets/readme/
│   ├── hero.svg                # README hero
│   └── community-qr.png        # community QR code
├── README.md
└── LICENSE
```

## License

MIT — use it freely, attribution optional.

---

## 🛠️ Need customization?

**Agent & Skills customization, from ¥800 (≈$110).**

- WeChat: `dtsola` (note: **openclaw custom**)
- Services: OpenClaw multi-agent deployment / workspace standardization / custom Skill development / usage monitoring & optimization

## 💬 Join the community

Xiaoyao product family user group — feedback · exchange · suggestions:

<p align="center">
  <img src="./assets/readme/community-qr.png" width="280" alt="XiaoyaoAI user group QR: scan to join, or add WeChat dtsola (note: 加群)">
</p>

<p align="center">Scan to join, or add WeChat <code>dtsola</code> (note: <b>加群</b>)</p>

## Sister projects

- 🏠 **xiaoyaoclaw-workspace-initializer** (workspace initializer): gives every agent a "home" — standard directory structure + WORKSPACE.md rules + multi-agent config safety. <https://github.com/dtsola/xiaoyaoclaw-workspace-initializer>
- 🧠 **xiaoyaoclaw-memory-distill** (memory distillation): turn conversations into structured memory — semantic classification + first-run build + incremental dedup + sensitive-info skip. <https://github.com/dtsola/xiaoyaoclaw-memory-distill>
- 🗂️ **xiaoyaoclaw-task-progress-tracker** (task progress tracker): directory as container, PROGRESS.md as progress — lifecycle management for tasks/ and projects/. <https://github.com/dtsola/xiaoyaoclaw-task-progress-tracker>
- 📚 **xiaoyaoclaw-kb-retriever** (knowledge base retriever): local KB retrieval — hierarchical data_structure.md index + progressive retrieval over md/pdf/xlsx, zero-dependency, Windows & macOS. <https://github.com/dtsola/xiaoyaoclaw-kb-retriever>
- 🩹 **xiaoyaoclaw-workspace-auditor**: read-only workspace health check — 5 categories, graded report with fix suggestions, zero-dependency, never modifies files. <https://github.com/dtsola/xiaoyaoclaw-workspace-auditor>
- 📎 **xiaoyaoclaw-web-clipper**: save any web page as clean local Markdown with frontmatter — dual-engine extraction (readability + trafilatura fallback), Chinese-safe filenames, batch clipping with dedup; feeds knowledge/clippings/ for kb-retriever. <https://github.com/dtsola/xiaoyaoclaw-web-clipper>
- 🤝 **xiaoyaoclaw-agent-orchestrator** (agent orchestrator): split tasks, dispatch to agents, track progress, aggregate results, retry on failure — daily multi-agent coordination. <https://github.com/dtsola/xiaoyaoclaw-agent-orchestrator>
- 🎛️ **xiaoyaoclaw-commander** (cross-tool commander, **command layer**): command your XiaoyaoClaw/OpenClaw multi-agent system from any Agent Skills tool (Claude Code / Codex / OpenCode / Trae / DSH). <https://github.com/dtsola/xiaoyaoclaw-commander>
