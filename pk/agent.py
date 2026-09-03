# -*- coding: utf-8 -*-
"""写入 agent：拿到一段具体经历，自己去查库，然后决定 link 什么、猜什么。

两阶段。第一阶段 agent 自己出查询词（可以来回多轮），第二阶段基于查到的候选写入。
「自己跟库交互」是硬要求 —— 系统不替它预筛候选。
"""
import json

from pk.store import Store, POS, NEG

MODEL = "claude-opus-5"

SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "queries": {"type": "array", "items": {"type": "string"},
                    "description": "想查的关键词/说法；想不出新的就给空数组"},
        "done": {"type": "boolean", "description": "候选够了就 true"},
    },
    "required": ["queries", "done"], "additionalProperties": False,
}

WRITE_SCHEMA = {
    "type": "object",
    "properties": {
        "links": {"type": "array", "items": {
            "type": "object",
            "properties": {"target": {"type": "string", "description": "已有节点 id"},
                           "polarity": {"type": "string", "enum": ["+", "-"]},
                           "why": {"type": "string"}},
            "required": ["target", "polarity", "why"], "additionalProperties": False}},
        "new_phenomena": {"type": "array", "items": {"type": "string"},
                          "description": "猜的现象 pattern，尽量猜，粒度可以不同"},
        "new_solutions": {"type": "array", "items": {"type": "string"},
                          "description": "猜的解法 pattern；这次没做干预就给空"},
        "new_conditions": {"type": "array", "items": {
            "type": "object",
            "properties": {"claim": {"type": "string"},
                           "test": {"type": "string", "description": "怎么判断满不满足"}},
            "required": ["claim", "test"], "additionalProperties": False}},
        "prescription": {
            "type": "object",
            "description": "有干预且知道结果时才给；用 id 或上面新猜的原文来指代",
            "properties": {"phenomenon": {"type": "string"},
                           "conditions": {"type": "array", "items": {"type": "string"}},
                           "solution": {"type": "string"},
                           "outcome": {"type": "string", "enum": ["worked", "failed", "none"]}},
            "required": ["phenomenon", "conditions", "solution", "outcome"],
            "additionalProperties": False},
    },
    "required": ["links", "new_phenomena", "new_solutions", "new_conditions", "prescription"],
    "additionalProperties": False,
}

SYSTEM = """你在往一个跨行业的共享 pattern 库里写东西。库里的 pattern 都是别的 agent 猜出来的假说。

规则：
- 每次写入都必须给出要 link 的 pattern，能 link 多少 link 多少 —— 一件事可以同时是多个假说的证据。
- 正 link = 我这件事是它的一个实例；负 link = 我这件事反驳它，或它在我这个情形下不成立。
- 鼓励猜新的 pattern，粒度不确定就多猜几个不同层级的。
- 条件是一等公民：一个解法在什么约束下才成立，必须说清楚，并且写成可复用、可判断的谓词。
- 只有真的相关才 link。不确定相关就别 link —— 但明确不成立要打负 link，那比正 link 更值钱。"""


def _fmt(nodes):
    out = []
    for n in nodes:
        if n["kind"] == "pattern":
            out.append(f"- {n['id']} [{n['side']}/阶{n['order']}] {n['claim']}")
        elif n["kind"] == "condition":
            out.append(f"- {n['id']} [条件] {n['claim']}（判断：{n['test']}）")
        else:
            out.append(f"- {n['id']} [item] {n['what']}")
    return "\n".join(out) or "（没查到）"


class Writer:
    def __init__(self, store: Store, source: str, effort="low"):
        import anthropic
        self.client = anthropic.Anthropic()
        self.s, self.source, self.effort = store, source, effort
        self.tokens = 0

    def _ask(self, prompt, schema):
        r = self.client.messages.create(
            model=MODEL, max_tokens=8000, system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            thinking={"type": "adaptive"},
            output_config={"effort": self.effort,
                           "format": {"type": "json_schema", "schema": schema}},
        )
        self.tokens += r.usage.input_tokens + r.usage.output_tokens
        return json.loads(next(b.text for b in r.content if b.type == "text"))

    def explore(self, experience, rounds=3):
        """agent 自己出查询词去翻库，最多 rounds 轮。"""
        seen, hits = set(), []
        for _ in range(rounds):
            r = self._ask(
                f"我遇到的事：{experience}\n\n"
                f"我目前从库里翻到的：\n{_fmt(hits)}\n\n"
                "还想查什么？给几个查询说法。够了就 done=true。", SEARCH_SCHEMA)
            for q in r["queries"]:
                for n in self.s.search(q):
                    if n["id"] not in seen:
                        seen.add(n["id"])
                        hits.append(n)
            if r["done"] or not r["queries"]:
                break
        return hits

    def write(self, what, facts=None, intervention=None, outcome="unknown"):
        exp = what + (f"\n我做的干预：{intervention}（结果：{outcome}）" if intervention else "")
        cands = self.explore(exp)
        plan = self._ask(
            f"我遇到的事：{exp}\n\n库里查到的候选：\n{_fmt(cands)}\n\n"
            "决定：link 哪些（正/负）、猜哪些新 pattern 和条件、以及（有干预时）"
            "一条 (现象 + 条件集合) -> 解法 的 prescription。", WRITE_SCHEMA)

        item = self.s.add_item(what, self.source, intervention, outcome)
        by_claim = {}
        for l in plan["links"]:
            if l["target"] in self.s.nodes:
                self.s.link(item, l["target"], l["why"], self.source, l["polarity"])
        for c in plan["new_phenomena"]:
            by_claim[c] = self.s.add_pattern(c, "phenomenon", self.source)
            self.s.link(item, by_claim[c], "自己猜的", self.source)
        for c in plan["new_solutions"]:
            by_claim[c] = self.s.add_pattern(c, "solution", self.source)
        for c in plan["new_conditions"]:
            by_claim[c["claim"]] = self.s.add_condition(c["claim"], c["test"], self.source)

        rx = plan["prescription"]
        if rx["outcome"] != "none":
            resolve = lambda t: t if t in self.s.nodes else by_claim.get(t)
            ph, sol = resolve(rx["phenomenon"]), resolve(rx["solution"])
            conds = [c for c in map(resolve, rx["conditions"]) if c]
            if ph and sol:
                pid = self.s.prescribe(ph, conds, sol, self.source)
                self.s.record_application(pid, item, rx["outcome"], self.source)
        return item, plan
