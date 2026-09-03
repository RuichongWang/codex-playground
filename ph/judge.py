"""选择器。层级下钻和平铺检索共用同一个 judge —— 差异只来自结构，不来自模型。"""
import json

MODEL = "claude-opus-5"

SCHEMA = {
    "type": "object",
    "properties": {
        "question": {"type": "string", "description": "要在这些候选里做选择，必须先确认关于任务的哪一件事"},
        "answer": {"type": "string", "description": "根据任务描述回答上面那个问题"},
        "choice": {"type": "string", "description": "选中候选的 id；都不适用填 NONE"},
        "second": {"type": "string", "description": "次优候选的 id；没有填 NONE"},
        "confident": {"type": "boolean"},
    },
    "required": ["question", "answer", "choice", "second", "confident"],
    "additionalProperties": False,
}

SYSTEM = (
    "你在一个「做法层级」里导航，目标是找到能解决当前任务的那条做法。\n"
    "每一步给你一组候选。不要问『哪个看起来最像任务描述』—— 描述是间接说法，字面相似没有意义。\n"
    "先想清楚：要在这些候选之间做选择，我必须先确认关于这个任务的哪一件事？"
    "回答它，再据此选。候选里确实没有适用的，就选 NONE。"
)


def _prompt(task, cands, path):
    lines = [f"任务：{task}", ""]
    if path:
        lines += ["已走过的路径：" + " → ".join(path), ""]
    lines.append("候选：")
    for c in cands:
        vs = f"  ｜与兄弟的区别：{c['vs_siblings']}" if c.get("vs_siblings") else ""
        lines.append(f"- {c['id']}：{c['name']}{vs}")
    return "\n".join(lines)


class AnthropicJudge:
    def __init__(self, effort="low"):
        import anthropic
        self.client = anthropic.Anthropic()
        self.effort = effort
        self.tokens = 0
        self.calls = 0

    def choose(self, task, cands, path=()):
        r = self.client.messages.create(
            model=MODEL,
            max_tokens=8000,
            system=SYSTEM,
            messages=[{"role": "user", "content": _prompt(task, cands, path)}],
            thinking={"type": "adaptive"},
            output_config={"effort": self.effort,
                           "format": {"type": "json_schema", "schema": SCHEMA}},
        )
        self.calls += 1
        self.tokens += r.usage.input_tokens + r.usage.output_tokens
        text = next(b.text for b in r.content if b.type == "text")
        return json.loads(text)


def bigrams(s):
    return {s[i:i + 2] for i in range(len(s) - 1)}


def lexical(a, b):
    x, y = bigrams(a), bigrams(b)
    return len(x & y) / max(1, len(x | y))


class MockJudge:
    """无 API key 时跑通管线用：纯字面相似度选。也顺便是 flat 检索的字面上界参考。"""

    def __init__(self, **_):
        self.tokens = 0
        self.calls = 0

    def choose(self, task, cands, path=()):
        self.calls += 1
        ranked = sorted(cands, key=lambda c: -lexical(task, c["name"] + c.get("vs_siblings", "")))
        return {"question": "", "answer": "", "choice": ranked[0]["id"],
                "second": ranked[1]["id"] if len(ranked) > 1 else "NONE", "confident": True}
