#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
usage-report.py — OpenClaw 性能用量查询工具（零依赖，纯标准库）

数据源：OpenClaw session JSONL（state/agents/*/sessions/*.jsonl）
能力：
  - 按 agent / 模型 / 日期 聚合 token + 成本 + 平均耗时
  - 按工具聚合：调用次数 / 平均耗时 / 失败率 / 总耗时
  - 按任务(session)聚合：起止时间、模型序列、总 token、总耗时
  - skills 使用统计（从 read 工具参数推断 SKILL.md）
  - 支持 --today / --week / --all / --agent / --by-model / --by-tool / --skills / --json

统计口径（重要）：
  - 真实 token 消耗 = input + output（totalTokens 含 cacheRead 会在每轮重复计数，禁用）
  - 工具耗时 = toolResult.timestamp - 对应 toolCall 所在 assistant message.timestamp
  - 任务耗时 = session 内最后一条消息.timestamp - 第一条用户消息.timestamp
"""

import argparse
import glob
import io
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DEFAULT_STATE = r"C:\Users\Administrator\AppData\Roaming\xiaoyaoclaw-desktop\runtime\openclaw\state"


def parse_ts(ts):
    """解析 ISO 时间戳 -> epoch ms"""
    if isinstance(ts, (int, float)):
        return int(ts)
    if isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except ValueError:
            return None
    return None


def find_session_files(state_dir):
    """扫描所有 agent 的 session jsonl"""
    files = []
    for agent_dir in glob.glob(os.path.join(state_dir, "agents", "*")):
        if not os.path.isdir(agent_dir):
            continue
        agent = os.path.basename(agent_dir)
        for f in glob.glob(os.path.join(agent_dir, "sessions", "*.jsonl")):
            files.append((agent, f))
    return files


def iter_events(agent, path):
    """逐行解析 jsonl，产出 (event, agent)"""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                    ev["_agent"] = agent
                    yield ev
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


def extract_tool_calls(msg):
    """从 assistant message content 提取 toolCall 列表"""
    calls = []
    content = msg.get("content") or []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "toolCall":
                calls.append(block)
    return calls


def is_skill_read(tool_name, args):
    """判断 read 工具是否读取了技能文件，返回技能名或 None"""
    if tool_name != "read":
        return None
    fp = ""
    if isinstance(args, dict):
        fp = str(args.get("file_path") or args.get("path") or "")
    elif isinstance(args, str):
        fp = args
    norm = fp.replace("\\", "/").lower()
    if "/skills/" in norm and norm.endswith(".md"):
        # 提取 skills/<name>/SKILL.md 或 skills/<name>.md
        parts = norm.split("/skills/")[-1].split("/")
        if parts:
            name = parts[0]
            if name.endswith(".md"):
                name = name[:-3]
            return name
    return None


def analyze(state_dir):
    """主分析：返回结构化结果"""
    agents = defaultdict(lambda: defaultdict(lambda: {"tokens_in": 0, "tokens_out": 0,
                                                      "cache_read": 0, "cache_write": 0,
                                                      "cost": 0.0, "calls": 0,
                                                      "total_ms": 0, "max_ms": 0}))
    tools = defaultdict(lambda: {"count": 0, "errors": 0, "total_ms": 0,
                                 "max_ms": 0, "min_ms": None, "agents": set()})
    skills = defaultdict(lambda: {"count": 0, "agents": set()})
    sessions = []  # (agent, session_id, start, end, models, tokens, cost, tools, msgs)
    daily = defaultdict(lambda: {"tokens_in": 0, "tokens_out": 0, "cost": 0.0, "calls": 0,
                                 "agents": defaultdict(lambda: {"tokens_in": 0, "tokens_out": 0,
                                                                "cost": 0.0, "calls": 0})})

    files = find_session_files(state_dir)
    if not files:
        print(f"[WARN] 未找到 session 文件: {state_dir}")
        return None

    for agent, path in files:
        # 先收集当前 session 的所有事件
        events = list(iter_events(agent, path))
        if not events:
            continue
        session_id = None
        pend_calls = {}  # toolCallId -> (toolName, ts)
        s_start = None
        s_end = None
        s_models = set()
        s_tokens = {"in": 0, "out": 0}
        s_cost = 0.0
        s_model_ms = 0
        s_tools = set()
        s_msgs = 0
        # 活跃耗时：相邻事件间隔 < 5min 的累计（排除用户思考间隔）
        ev_ts_list = []
        for ev in events:
            t = parse_ts(ev.get("timestamp"))
            if t:
                ev_ts_list.append((t, ev.get("type")))
        active_ms = 0
        for i in range(1, len(ev_ts_list)):
            gap = ev_ts_list[i][0] - ev_ts_list[i - 1][0]
            if 0 < gap < 300000:
                active_ms += gap

        prev_ev_ts = None
        for ev in events:
            etype = ev.get("type")
            ts = parse_ts(ev.get("timestamp"))
            if etype == "session":
                session_id = ev.get("id")
            elif etype == "message":
                msg = ev.get("message") or {}
                role = msg.get("role")
                mts = parse_ts(msg.get("timestamp")) or ts
                if mts:
                    if s_start is None or mts < s_start:
                        s_start = mts
                    if s_end is None or mts > s_end:
                        s_end = mts
                s_msgs += 1

                usage = msg.get("usage") or {}
                tin = usage.get("input") or 0
                tout = usage.get("output") or 0
                cr = usage.get("cacheRead") or 0
                cw = usage.get("cacheWrite") or 0
                cost = 0.0
                c = usage.get("cost")
                if isinstance(c, dict):
                    cost = float(c.get("total") or 0)
                elif isinstance(c, (int, float)):
                    cost = float(c)

                model = msg.get("model") or "unknown"
                provider = msg.get("provider") or "unknown"

                if role == "assistant":
                    # 模型调用记录（usage 有值才算一次真实调用）
                    if usage:
                        mkey = f"{provider}/{model}"
                        agents[agent][mkey]["tokens_in"] += tin
                        agents[agent][mkey]["tokens_out"] += tout
                        agents[agent][mkey]["cache_read"] += cr
                        agents[agent][mkey]["cache_write"] += cw
                        agents[agent][mkey]["cost"] += cost
                        agents[agent][mkey]["calls"] += 1
                        # 模型耗时估算：本事件 ts − 前一条事件 ts（0 < gap < 10min）。
                        # ⚠️ 不能用 message.timestamp（批量写入时间戳，非推理耗时）。
                        # 语义：assistant 的前一条事件是 user 或 toolResult → 间隔 ≈ 模型接收上下文+生成回复。
                        if prev_ev_ts and ts:
                            llm_dur = ts - prev_ev_ts
                            if 0 < llm_dur < 600000:
                                agents[agent][mkey]["total_ms"] += llm_dur
                                agents[agent][mkey]["max_ms"] = max(agents[agent][mkey]["max_ms"], llm_dur)
                                s_model_ms += llm_dur
                        s_tokens["in"] += tin
                        s_tokens["out"] += tout
                        s_cost += cost
                        s_models.add(mkey)
                        daily_key = datetime.fromtimestamp(mts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                        daily[daily_key]["tokens_in"] += tin
                        daily[daily_key]["tokens_out"] += tout
                        daily[daily_key]["cost"] += cost
                        daily[daily_key]["calls"] += 1
                        daily[daily_key]["agents"][agent]["tokens_in"] += tin
                        daily[daily_key]["agents"][agent]["tokens_out"] += tout
                        daily[daily_key]["agents"][agent]["cost"] += cost
                        daily[daily_key]["agents"][agent]["calls"] += 1

                    # 工具调用发起
                    for tc in extract_tool_calls(msg):
                        tid = tc.get("id")
                        tname = tc.get("name") or "?"
                        pend_calls[tid] = (tname, mts)
                        s_tools.add(tname)

                elif role == "toolResult":
                    tid = ev.get("toolCallId") or msg.get("toolCallId")
                    tname = msg.get("toolName") or "?"
                    is_err = bool(msg.get("isError"))
                    rts = parse_ts(msg.get("timestamp")) or mts
                    s_tools.add(tname)
                    if tid in pend_calls:
                        pname, pts = pend_calls.pop(tid)
                        dur = (rts - pts) if (rts and pts) else 0
                        tools[pname]["count"] += 1
                        tools[pname]["total_ms"] += dur
                        tools[pname]["max_ms"] = max(tools[pname]["max_ms"], dur)
                        tools[pname]["min_ms"] = dur if tools[pname]["min_ms"] is None else min(tools[pname]["min_ms"], dur)
                        tools[pname]["agents"].add(agent)
                        if is_err:
                            tools[pname]["errors"] += 1
                    else:
                        # 无配对（如截断）也计数
                        tools[tname]["count"] += 1
                        tools[tname]["agents"].add(agent)
                        if is_err:
                            tools[tname]["errors"] += 1

                # 任务耗时窗口：只要 session 有消息就累计
            elif etype == "custom" and ev.get("customType") == "model-snapshot":
                pass
            # 事件顶层 ts 作为序列基准（真实处理时序）
            if ts:
                prev_ev_ts = ts

        # 从 assistant toolCall 补 skills 推断（参数在 arguments 里）
        for ev in events:
            if ev.get("type") == "message":
                msg = ev.get("message") or {}
                if msg.get("role") == "assistant":
                    for tc in extract_tool_calls(msg):
                        sk = is_skill_read(tc.get("name"), tc.get("arguments"))
                        if sk:
                            skills[sk]["count"] += 1
                            skills[sk]["agents"].add(agent)

        if session_id:
            sessions.append({
                "agent": agent,
                "id": session_id,
                "start": s_start,
                "end": s_end,
                "duration_ms": (s_end - s_start) if (s_start and s_end) else 0,
                "active_ms": active_ms,
                "model_ms": s_model_ms,
                "models": sorted(s_models),
                "tokens": s_tokens["in"] + s_tokens["out"],
                "cost": s_cost,
                "tools": sorted(s_tools),
                "msgs": s_msgs,
            })

    return {
        "agents": agents,
        "tools": tools,
        "skills": skills,
        "sessions": sessions,
        "daily": daily,
    }


def fmt_ms(ms):
    if ms is None:
        return "-"
    if ms < 1000:
        return f"{ms:.0f}ms"
    if ms < 60000:
        return f"{ms/1000:.1f}s"
    return f"{ms/60000:.1f}m"


def apply_agent_filter(r, agent_name):
    """按 agent 过滤所有维度（agents/tools/skills/sessions/daily）。
    必须在窗口过滤之前、输出之前调用，保证 --agent 对每个维度都生效。"""
    if not agent_name:
        return r
    r = dict(r)
    r["agents"] = {a: mm for a, mm in r["agents"].items() if a == agent_name}
    r["tools"] = {t: d for t, d in r["tools"].items() if agent_name in d["agents"]}
    r["skills"] = {s: d for s, d in r["skills"].items() if agent_name in d["agents"]}
    r["sessions"] = [s for s in r["sessions"] if s["agent"] == agent_name]
    # daily：只保留该 agent 的每日数据（无数据的天剔除）
    r["daily"] = {k: v for k, v in r["daily"].items() if agent_name in v["agents"]}
    for v in r["daily"].values():
        v["tokens_in"] = v["agents"][agent_name]["tokens_in"]
        v["tokens_out"] = v["agents"][agent_name]["tokens_out"]
        v["cost"] = v["agents"][agent_name]["cost"]
        v["calls"] = v["agents"][agent_name]["calls"]
        v["agents"] = {agent_name: v["agents"][agent_name]}
    return r


def in_window(ts, args, now=None):
    """按 --today / --week 窗口过滤时间戳（模块级，report 与 JSON 共用）"""
    if not ts:
        return False
    now = now or datetime.now(timezone.utc)
    dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
    if args.today:
        return dt.date() == now.date()
    if args.week:
        return dt >= now - timedelta(days=7)
    return True


def report(r, args):
    out = []
    now = datetime.now(timezone.utc)

    # 过滤 sessions
    sess = [s for s in r["sessions"] if in_window(s["start"], args, now)]

    # 过滤 daily（按窗口）
    daily = {k: v for k, v in r["daily"].items()
             if in_window(datetime.strptime(k, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000, args, now)}

    out.append("=" * 60)
    out.append("OpenClaw 用量报告")
    out.append(f"时间范围: {'今天' if args.today else '近7天' if args.week else '全部'} | "
               f"agent 过滤: {args.agent or '全部'} | sessions: {len(sess)}")
    out.append("=" * 60)

    # 1. 汇总
    tot_in = sum(s["tokens"] for s in sess)  # 简化：sessions 聚合
    tot_ms = sum(s["duration_ms"] for s in sess)
    out.append(f"\n📊 总览: {len(sess)} 个任务 | 总 token(input+output): {tot_in:,} | "
               f"总耗时: {fmt_ms(tot_ms)}")
    out.append("  (任务耗时 = session 首条用户消息 → 末条消息，含用户思考间隔；成本维度已按需移除，token 为主指标)")

    # 2. 按 agent + 模型
    out.append("\n📦 按 agent / 模型（token=input+output 真实消耗；模型耗时≈本消息ts−前事件ts，cap 10min）:")
    out.append(f"  {'Agent':<10}{'模型':<28}{'调用':>6}{'输入tok':>12}{'输出tok':>12}{'模型总耗时':>12}{'平均':>10}")
    for agent in sorted(r["agents"]):
        for mkey in sorted(r["agents"][agent]):
            d = r["agents"][agent][mkey]
            if mkey.endswith("/delivery-mirror"):
                continue  # 虚拟投递模型，跳过
            avg = d["total_ms"] / d["calls"] if d["calls"] else 0
            out.append(f"  {agent:<10}{mkey:<28}{d['calls']:>6}{d['tokens_in']:>12,}"
                       f"{d['tokens_out']:>12,}{fmt_ms(d['total_ms']):>12}{fmt_ms(avg):>10}")

    # 3. 按工具
    if args.by_tool:
        out.append("\n🔧 按工具（耗时 = toolResult - toolCall）:")
        out.append(f"  {'工具':<22}{'次数':>6}{'失败':>6}{'总耗时':>10}{'平均':>10}{'最慢':>10}")
        for t in sorted(r["tools"], key=lambda x: -r["tools"][x]["total_ms"]):
            d = r["tools"][t]
            avg = d["total_ms"] / d["count"] if d["count"] else 0
            out.append(f"  {t:<22}{d['count']:>6}{d['errors']:>6}{fmt_ms(d['total_ms']):>10}"
                       f"{fmt_ms(avg):>10}{fmt_ms(d['max_ms']):>10}")

    # 4. skills
    if args.skills:
        out.append("\n📚 Skills 使用（从 read 调用推断）:")
        out.append(f"  {'技能':<30}{'读取次数':>8}{'使用 agent':>20}")
        for sk in sorted(r["skills"], key=lambda x: -r["skills"][x]["count"]):
            d = r["skills"][sk]
            out.append(f"  {sk:<30}{d['count']:>8}{','.join(sorted(d['agents'])):>20}")

    # 5. 任务排行（按耗时）
    if args.by_session:
        out.append("\n⏱️ 任务排行（活跃=相邻事件间隔<5min 累计，排除用户思考；模型耗时=事件ts间隔近似，cap 10min）:")
        out.append(f"  {'Agent':<10}{'活跃耗时':>10}{'窗口耗时':>10}{'模型耗时':>10}{'token':>12}{'消息':>6}  模型")
        key = (lambda x: -x["model_ms"]) if args.by_model_time else (lambda x: -x["active_ms"])
        for s in sorted(sess, key=key)[:20]:
            out.append(f"  {s['agent']:<10}{fmt_ms(s['active_ms']):>10}{fmt_ms(s['duration_ms']):>10}"
                       f"{fmt_ms(s['model_ms']):>10}{s['tokens']:>12,}{s['msgs']:>6}  {','.join(s['models'])[:60]}")

    # 6. 每日趋势
    if args.daily:
        out.append("\n📅 每日趋势:")
        out.append(f"  {'日期':<12}{'输入tok':>12}{'输出tok':>12}{'调用':>8}")
        for day in sorted(daily):
            d = daily[day]
            out.append(f"  {day:<12}{d['tokens_in']:>12,}{d['tokens_out']:>12,}{d['calls']:>8}")

    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="OpenClaw 用量/性能查询")
    ap.add_argument("--state", default=os.environ.get("OPENCLAW_STATE", DEFAULT_STATE),
                    help="OpenClaw state 目录（默认自动检测）")
    ap.add_argument("--today", action="store_true", help="仅今天")
    ap.add_argument("--week", action="store_true", help="近 7 天")
    ap.add_argument("--agent", default=None, help="按 agent 过滤")
    ap.add_argument("--by-tool", action="store_true", help="工具耗时明细")
    ap.add_argument("--skills", action="store_true", help="skills 使用统计")
    ap.add_argument("--by-session", action="store_true", help="任务耗时排行")
    ap.add_argument("--by-model-time", action="store_true", help="任务排行按模型耗时排序")
    ap.add_argument("--daily", action="store_true", help="每日趋势")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()

    r = analyze(args.state)
    if r is None:
        sys.exit(1)

    # 统一按 agent 过滤（对所有维度生效，report 与 JSON 共用）
    r = apply_agent_filter(r, args.agent)

    if args.json:
        # 简化 JSON：只输出核心聚合（按窗口过滤 daily，与文本输出一致）
        slim = {
            "agents": {a: {m: d for m, d in mm.items()} for a, mm in r["agents"].items()},
            "tools": {t: {**d, "agents": sorted(d["agents"])} for t, d in r["tools"].items()},
            "skills": {k: {"count": v["count"], "agents": sorted(v["agents"])} for k, v in r["skills"].items()},
            "sessions": [s for s in r["sessions"] if in_window(s["start"], args)],
            "daily": {k: v for k, v in r["daily"].items()
                      if in_window(datetime.strptime(k, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000, args)},
        }
        print(json.dumps(slim, ensure_ascii=False, indent=1))
    else:
        # 默认全开（含工具明细）
        args.by_tool = args.by_tool or True
        args.skills = args.skills or True
        args.by_session = args.by_session or True
        args.daily = args.daily or True
        print(report(r, args))


if __name__ == "__main__":
    main()
