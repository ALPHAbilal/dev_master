#!/usr/bin/env python3
"""Stream a Claude Code .jsonl transcript -> compact conversation spine.
Never holds more than one line in memory. Emits JSONL digest + stats.
"""
import json, sys, os, re
from collections import Counter

def txt(content):
    """Flatten a message .content into (text, tool_names, tool_result_bytes)."""
    if isinstance(content, str):
        return content, [], 0
    parts, tools, res = [], [], 0
    if not isinstance(content, list):
        return "", [], 0
    for b in content:
        if not isinstance(b, dict):
            continue
        t = b.get("type")
        if t == "text":
            parts.append(b.get("text", ""))
        elif t == "thinking":
            parts.append("[THINKING] " + b.get("thinking", "")[:400])
        elif t == "tool_use":
            name = b.get("name", "?")
            inp = b.get("input", {})
            hint = ""
            if isinstance(inp, dict):
                for k in ("description", "command", "file_path", "pattern", "skill", "prompt"):
                    if k in inp and isinstance(inp[k], str):
                        hint = inp[k][:90].replace("\n", " ")
                        break
            tools.append(f"{name}({hint})")
        elif t == "tool_result":
            c = b.get("content")
            res += len(json.dumps(c)) if c is not None else 0
    return "\n".join(parts), tools, res

def main(path, out):
    stats = Counter()
    turns = []
    with open(path, "r", errors="replace") as f:
        for ln, line in enumerate(f):
            stats["lines"] += 1
            stats["bytes"] += len(line)
            try:
                d = json.loads(line)
            except Exception:
                stats["bad_json"] += 1
                continue
            typ = d.get("type")
            stats["type:" + str(typ)] += 1
            ts = (d.get("timestamp") or "")[:19]
            msg = d.get("message") or {}
            content = msg.get("content")
            text, tools, resbytes = txt(content)
            is_meta = d.get("isMeta", False)
            side = d.get("isSidechain", False)

            if typ == "user":
                kind = "user"
                if is_meta or text.startswith("<system-reminder>") or text.startswith("<command-name>"):
                    kind = "meta"
                if not text.strip() and resbytes:
                    kind = "toolresult"
                    stats["tool_result_bytes"] += resbytes
                if kind == "user":
                    stats["user_turns"] += 1
                turns.append({"i": ln, "ts": ts, "k": kind, "side": side,
                              "t": text[:4000], "len": len(text), "rb": resbytes})
            elif typ == "assistant":
                u = msg.get("usage") or {}
                stats["out_tok"] += u.get("output_tokens", 0) or 0
                stats["cache_read"] += u.get("cache_read_input_tokens", 0) or 0
                stats["cache_write"] += u.get("cache_creation_input_tokens", 0) or 0
                for t in tools:
                    stats["tool:" + t.split("(")[0]] += 1
                turns.append({"i": ln, "ts": ts, "k": "asst", "side": side,
                              "t": text[:2500], "len": len(text), "tools": tools,
                              "model": msg.get("model", "")})
            elif typ == "system":
                turns.append({"i": ln, "ts": ts, "k": "sys", "side": side,
                              "t": (d.get("content") or "")[:600]})
            else:
                turns.append({"i": ln, "ts": ts, "k": str(typ), "side": side, "t": str(d)[:300]})

    with open(out, "w") as g:
        for t in turns:
            g.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in sorted(stats.items())}, indent=1))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
