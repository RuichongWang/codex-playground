# -*- coding: utf-8 -*-
"""把全量轨迹压成可留档的提炼版：工具调用序列 + 碰过的节点 id。

原始 stream-json 每个约 600KB，只有分析价值没有留档价值。
提炼版保留能复现分析的全部信息，体积约 1%。
"""
import argparse, glob, json, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = re.compile(r"\b([PCIR]\d{1,4})\b")


def digest(path):
    calls, nodes = [], {}
    for line in open(path):
        try:
            ev = json.loads(line)
        except Exception:
            continue
        t = ev.get("type")
        blocks = ev.get("message", {}).get("content", []) if t in ("assistant", "user") else []
        if not isinstance(blocks, list):
            continue
        for b in blocks:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                inp = b.get("input", {})
                calls.append((inp.get("command") or json.dumps(inp, ensure_ascii=False))[:220])
                txt = json.dumps(inp, ensure_ascii=False)
            elif b.get("type") == "tool_result":
                c = b.get("content")
                txt = c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
            elif b.get("type") == "text":
                txt = b.get("text", "")
            else:
                continue
            for m in NODE.findall(txt or ""):
                nodes[m] = nodes.get(m, 0) + 1
    return dict(calls=calls, nodes=nodes)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="runs/stage4"); a = ap.parse_args()
    d = os.path.join(ROOT, a.out)
    rows = []
    for f in sorted(glob.glob(os.path.join(d, "trace_*.jsonl"))):
        b = os.path.basename(f)[len("trace_"):-len(".jsonl")]
        cid, _, arm = b.rpartition("_")
        r = digest(f)
        rows.append(dict(id=cid, arm=arm, n_calls=len(r["calls"]), calls=r["calls"], nodes=r["nodes"]))
    p = os.path.join(d, "trace_digest.jsonl")
    with open(p, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(rows)} 条轨迹 -> {p}  ({os.path.getsize(p)//1024}KB)")


if __name__ == "__main__":
    main()
