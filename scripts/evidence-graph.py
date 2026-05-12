#!/usr/bin/env python3
"""V8: Evidence graph v3 foundation (PRD §10.2).

Lightweight provenance graph layered on top of ledger v2. Records claims,
validations, artifacts, and derived-from links. Reversible migration:
ledger v2 stays canonical; evidence graph is read-only projection.

Subcommands:
  evidence-graph.py write-claim ...
  evidence-graph.py write-validation ...
  evidence-graph.py write-artifact ...
  evidence-graph.py link <from> <to> <relation>
  evidence-graph.py query [--node <id>] [--relation <r>]
  evidence-graph.py path                       # storage path
  evidence-graph.py stats
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path


def graph_dir() -> Path:
    p = Path.home() / ".ultraprompt" / "evidence-graph"
    p.mkdir(parents=True, exist_ok=True)
    return p


def nodes_path() -> Path:
    return graph_dir() / "nodes.jsonl"


def edges_path() -> Path:
    return graph_dir() / "edges.jsonl"


def _gen_id(kind: str, *parts: str) -> str:
    h = hashlib.sha256()
    h.update(kind.encode())
    for p in parts:
        h.update(p.encode())
    h.update(str(time.time()).encode())
    return f"{kind}:{h.hexdigest()[:12]}"


def write_node(kind: str, **attrs) -> dict:
    """Write a node (claim, validation, artifact)."""
    node_id = attrs.get("id") or _gen_id(kind, *(str(v) for v in attrs.values()))
    record = {
        "id": node_id,
        "kind": kind,
        "ts": int(time.time()),
        **attrs,
    }
    with open(nodes_path(), "a") as f:
        f.write(json.dumps(record, default=str) + "\n")
    return record


def write_edge(from_id: str, to_id: str, relation: str, **attrs) -> dict:
    """Write an edge (derived-from, validates, refutes, supports, contradicts)."""
    record = {
        "from": from_id,
        "to": to_id,
        "relation": relation,
        "ts": int(time.time()),
        **attrs,
    }
    with open(edges_path(), "a") as f:
        f.write(json.dumps(record, default=str) + "\n")
    return record


def query_nodes(node_id: str | None = None, kind: str | None = None) -> list[dict]:
    if not nodes_path().exists():
        return []
    results = []
    for line in nodes_path().read_text().splitlines():
        try:
            n = json.loads(line)
            if node_id and n.get("id") != node_id:
                continue
            if kind and n.get("kind") != kind:
                continue
            results.append(n)
        except Exception:
            continue
    return results


def query_edges(node_id: str | None = None, relation: str | None = None) -> list[dict]:
    if not edges_path().exists():
        return []
    results = []
    for line in edges_path().read_text().splitlines():
        try:
            e = json.loads(line)
            if node_id and e.get("from") != node_id and e.get("to") != node_id:
                continue
            if relation and e.get("relation") != relation:
                continue
            results.append(e)
        except Exception:
            continue
    return results


def stats() -> dict:
    nodes = query_nodes()
    edges = query_edges()
    return {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "by_kind": {k: sum(1 for n in nodes if n.get("kind") == k)
                    for k in set(n.get("kind") for n in nodes)},
        "by_relation": {r: sum(1 for e in edges if e.get("relation") == r)
                        for r in set(e.get("relation") for e in edges)},
        "nodes_path": str(nodes_path()),
        "edges_path": str(edges_path()),
    }


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s_c = sub.add_parser("write-claim")
    s_c.add_argument("--text", required=True)
    s_c.add_argument("--source")
    s_c.add_argument("--confidence")
    s_v = sub.add_parser("write-validation")
    s_v.add_argument("--what-was-validated", required=True)
    s_v.add_argument("--method")
    s_v.add_argument("--result")
    s_a = sub.add_parser("write-artifact")
    s_a.add_argument("--artifact-type", required=True)
    s_a.add_argument("--path")
    s_l = sub.add_parser("link")
    s_l.add_argument("from_id")
    s_l.add_argument("to_id")
    s_l.add_argument("relation",
                     choices=["derived-from", "validates", "refutes", "supports", "contradicts"])
    s_q = sub.add_parser("query")
    s_q.add_argument("--node")
    s_q.add_argument("--relation")
    sub.add_parser("path")
    sub.add_parser("stats")

    args = ap.parse_args()

    if args.cmd == "path":
        print(graph_dir())
        return 0
    if args.cmd == "stats":
        print(json.dumps(stats(), indent=2, default=str))
        return 0
    if args.cmd == "write-claim":
        attrs = {"text": args.text}
        if args.source: attrs["source"] = args.source
        if args.confidence: attrs["confidence"] = args.confidence
        r = write_node("claim", **attrs)
        print(json.dumps({"ok": True, "id": r["id"]}, indent=2))
        return 0
    if args.cmd == "write-validation":
        attrs = {"what_was_validated": args.what_was_validated}
        if args.method: attrs["method"] = args.method
        if args.result: attrs["result"] = args.result
        r = write_node("validation", **attrs)
        print(json.dumps({"ok": True, "id": r["id"]}, indent=2))
        return 0
    if args.cmd == "write-artifact":
        attrs = {"artifact_type": args.artifact_type}
        if args.path: attrs["path"] = args.path
        r = write_node("artifact", **attrs)
        print(json.dumps({"ok": True, "id": r["id"]}, indent=2))
        return 0
    if args.cmd == "link":
        r = write_edge(args.from_id, args.to_id, args.relation)
        print(json.dumps({"ok": True}, indent=2))
        return 0
    if args.cmd == "query":
        if args.node:
            n = query_nodes(node_id=args.node)
            e = query_edges(node_id=args.node)
            print(json.dumps({"nodes": n, "edges": e}, indent=2, default=str))
        elif args.relation:
            e = query_edges(relation=args.relation)
            print(json.dumps({"edges": e}, indent=2, default=str))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
