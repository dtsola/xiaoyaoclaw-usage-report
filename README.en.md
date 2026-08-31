<div align="center">

# OpenClaw Usage Report

**Usage & performance reporting for OpenClaw agents** — how long each task took, which tools/skills/models were used, and how many tokens were consumed.

Zero dependency · Local only · Data never leaves your machine

</div>

---

## Why

OpenClaw has no built-in per-task performance panel, but session JSONL files (`state/agents/*/sessions/*.jsonl`) already record timestamps and token usage for every task, tool call, and model call. This tool consumes that data directly — **no extra instrumentation, no external dependencies, no uploads**.

Use it for: usage baselines before optimizing, finding the slowest tools, per-agent token reconciliation, and skill usage inventory.

## Features

| Dimension | Description |
|-----------|-------------|
| Task duration | Wall-clock + active duration per task (excludes user thinking gaps) |
| Model tokens | Per agent/model: call count, input/output tokens (real usage = input+output) |
| Model latency | Estimated (event-ts gap), total & average per agent/model |
| Tool latency | Per tool: count, errors, total/avg/max duration — find bottlenecks |
| Skill usage | Inferred from `read` calls: skill name, load count, agents |
| Daily trend | Daily input/output tokens and call counts |
| MCP tools | Same structure as regular tools (toolCall/toolResult) — covered natively |

## Quick Start

```bash
# Today's report (all dimensions by default)
python scripts/usage-report.py --today

# Last 7 days
python scripts/usage-report.py --week

# All history
python scripts/usage-report.py --all

# Filter by agent
python scripts/usage-report.py --agent xiaoxia

# Tool latency only / skills only
python scripts/usage-report.py --by-tool
python scripts/usage-report.py --skills

# JSON output (pipe to other tools / cron daily report)
python scripts/usage-report.py --today --json > usage-report.json
```

The data directory is auto-detected (Windows XiaoyaoClaw: `C:\Users\<user>\AppData\Roaming\xiaoyaoclaw-desktop\runtime\openclaw\state`); override with `--state <path>` or the `OPENCLAW_STATE` env var.

## Statistics Rules (important)

1. **Real token usage = input + output**. `totalTokens` includes cacheRead (re-counted every turn; measured inflation 1.3x–14x+, up to 568x per message) — the script already avoids this.
2. **Tool duration = toolResult.ts − assistant(toolCall).ts**, includes the model's tool-call decision time (not pure execution time).
3. **Model latency is an estimate** (assistant event ts − previous event ts, capped at 10 min). ⚠️ Do not use `message.timestamp` (batch-write timestamp); exact duration lives only in the diagnostics-otel event layer.
4. **No cost dimension**: pricing differs per provider; tokens are the universal metric. To add costs, configure `models.providers.*.cost` in OpenClaw and extend.
5. **Skill stats** cover only skills actually loaded via `read` (metadata-injected but never loaded ones are not counted).

## Cron Daily Report (optional, user-configured)

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

## Limitations

- "Active duration" is approximate (gaps <5 min accumulated; may include heartbeats)
- Only JSONL version 3 sessions are supported
- Local data only (run per machine in multi-host setups)

## Requirements

- Python 3.8+ (standard library only, zero dependencies)
- Read access to the OpenClaw state directory (`state/agents/*/sessions/*.jsonl`)

## Sister Projects

- [xiaoyaoclaw-workspace-initializer](https://github.com/dtsola/xiaoyaoclaw-workspace-initializer)
- [xiaoyaoclaw-memory-distill](https://github.com/dtsola/xiaoyaoclaw-memory-distill)
- [xiaoyaoclaw-task-progress-tracker](https://github.com/dtsola/xiaoyaoclaw-task-progress-tracker)
- [xiaoyaoclaw-kb-retriever](https://github.com/dtsola/xiaoyaoclaw-kb-retriever)
- [xiaoyaoclaw-workspace-auditor](https://github.com/dtsola/xiaoyaoclaw-workspace-auditor)
- [xiaoyaoclaw-web-clipper](https://github.com/dtsola/xiaoyaoclaw-web-clipper)
- [xiaoyaoclaw-agent-orchestrator](https://github.com/dtsola/xiaoyaoclaw-agent-orchestrator)

## License

MIT © dtsola
