# -*- coding: utf-8 -*-
u"""必红用例与绿对照。**不计入 500 行硬顶** —— 否则那条硬顶会奖励少写用例。

约定:必红用例返回 True = 「它确实红了」;绿对照返回 True = 「正常那条路走通了」。
"""
import json
import os
import shutil
import subprocess
import tempfile

from done import card as C
from done import judge as J
from done import ledger as L
from done import rules as R

AUTO = {u"id": u"a1", u"问": u"跑得通吗?", u"过": u"是",
        u"判者": {u"cmd": u"true", u"答是": u"exit0"}, u"凭什么答": u"退出码"}
EYE = {u"id": u"a2", u"问": u"打开过源文件吗?", u"过": u"否",
       u"判者": {u"读者": u"冷读者"}, u"凭什么答": u"它用过的命令清单"}
REPORT = {u"a2": {u"答": u"否", u"引文": u"cat README.md",
                  u"证据": u"ls\ncat README.md\nmake check", u"judge": u"t"}}


class Sandbox(object):
    u"""一个临时 git 仓 + 一本空账 + 一张卡文件。"""

    def __enter__(self):
        self.d = tempfile.mkdtemp(prefix=u"done-t-")
        self.ledger = os.path.join(self.d, u"ledger.jsonl")
        self.repo = os.path.join(self.d, u"r")
        os.makedirs(self.repo)
        for c in (u"git init -q", u"git config user.email t@t", u"git config user.name t",
                  u"touch f", u"git add -A", u"git commit -qm one"):
            subprocess.check_call(c, cwd=self.repo, shell=True)
        self.cardfile = os.path.join(self.d, u"c.json")
        self.write([dict(AUTO), dict(EYE)])
        return self

    def write(self, accept, cid=u"C-t"):
        with open(self.cardfile, u"wb") as f:
            f.write(json.dumps({u"id": cid, u"题面": u"测试卡", u"accept": accept},
                               ensure_ascii=False).encode(u"utf-8"))

    def head(self):
        return L.head(self.ledger)

    def __exit__(self, *a):
        shutil.rmtree(self.d, ignore_errors=True)


def _red(fn):
    u"""跑一个该被拦住的动作:被拦住就是红。"""
    try:
        fn()
    except L.Refused:
        return True
    return False


# ── R1 账只能追加 ────────────────────────────────────────────────────
def r1_red():
    with Sandbox() as s:
        for i in range(3):
            L.append(s.ledger, u"t", {u"i": i}, s.head())
        raw = open(s.ledger, u"rb").read().decode(u"utf-8").splitlines()
        raw[1] = raw[1].replace(u'"i":1', u'"i":9')
        open(s.ledger, u"wb").write((u"\n".join(raw) + u"\n").encode(u"utf-8"))
        return not L.verify(s.ledger)[0]


def r1_green():
    with Sandbox() as s:
        for i in range(3):
            L.append(s.ledger, u"t", {u"i": i}, s.head())
        return L.verify(s.ledger)[0] and len(L.read(s.ledger)) == 3


# ── R2 至少一条 auto ─────────────────────────────────────────────────
def r2_red():
    return _red(lambda: C.validate([dict(EYE)]))


def r2_green():
    return C.validate([dict(AUTO), dict(EYE)])


# ── R3 accept 预注册即冻结 ───────────────────────────────────────────
def _open(s):
    C.open_card(s.ledger, s.cardfile, u"t", s.head())


def _judge(s, reports=None):
    return J.judge(s.ledger, s.cardfile, s.repo, u"HEAD", s.head(),
                   reports if reports is not None else REPORT)


def r3_red():
    with Sandbox() as s:
        _open(s)
        a = dict(AUTO)
        a[u"问"] = u"改松了吗?"
        s.write([a, dict(EYE)])
        return _red(lambda: _judge(s))


def r3_green():
    with Sandbox() as s:
        _open(s)
        return _judge(s)[u"body"][u"passed"] is True


# ── R4 判的那只手写不到账 ────────────────────────────────────────────
def r4_red():
    with Sandbox() as s:
        L.append(s.ledger, u"t", {}, s.head())
        if not _red(lambda: L.ReadOnly(s.ledger).append(u"t", {}, s.head())):
            return False
        # 第二半:auto 命令在 worktree 里写 .done/ledger.jsonl,真账必须纹丝不动
        a = dict(AUTO)
        a[u"判者"] = {u"cmd": u"mkdir -p .done && echo x >> .done/ledger.jsonl",
                      u"答是": u"exit0"}
        s.write([a, dict(EYE)])
        _open(s)
        before = s.head()
        _judge(s)
        return L.verify(s.ledger)[0] and L.read(s.ledger)[-2][u"hash"] == before


def r4_green():
    with Sandbox() as s:
        _open(s)
        row = _judge(s)
        return row[u"kind"] == u"verdict" and L.verify(s.ledger)[0]


# ── R5 逐条 · 带 evidence · 不合成 ───────────────────────────────────
def r5_red():
    no_ev = {u"lines": [{u"id": u"a1", u"passed": True}]}
    agg = {u"score": 0.85, u"lines": [{u"id": u"a1", u"passed": True, u"evidence": {u"exit": 0}}]}
    faked = {u"lines": [{u"id": u"a2", u"判者": u"冷读者", u"答": u"否", u"passed": True,
                         u"evidence": {u"引文": u"我编的", u"引文在证据里": False}}]}
    # 「没找到」不写搜了什么 —— 那正是那个免费答案
    lazy = {u"lines": [{u"id": u"a9", u"判者": u"冷读者", u"答": u"没找到", u"passed": True,
                        u"evidence": {u"judge": u"t"}}]}
    return (_red(lambda: J.validate_verdict(no_ev))
            and _red(lambda: J.validate_verdict(agg))
            and _red(lambda: J.validate_verdict(faked))
            and _red(lambda: J.validate_verdict(lazy)))


def r5_green():
    return J.validate_verdict({u"lines": [
        {u"id": u"a1", u"判者": u"cmd", u"答": u"是", u"passed": True, u"evidence": {u"exit": 0}},
        {u"id": u"a2", u"判者": u"冷读者", u"答": u"否", u"passed": True,
         u"evidence": {u"引文": u"cat README.md", u"引文在证据里": True}},
        {u"id": u"a9", u"判者": u"冷读者", u"答": u"没找到", u"passed": True,
         u"evidence": {u"搜了什么": u"逐条核了 README 里全部 5 条命令"}}]})


# ── R6 改 accept 必须留疤 ────────────────────────────────────────────
def r6_red():
    with Sandbox() as s:
        _open(s)
        a = dict(AUTO)
        a[u"问"] = u"换了吗?"
        s.write([a, dict(EYE)])
        return _red(lambda: C.amend(s.ledger, s.cardfile, u"", u"t", s.head()))


def r6_green():
    with Sandbox() as s:
        _open(s)
        _judge(s)
        if len(C.effective_verdicts(s.ledger, u"C-t")) != 1:
            return False
        a = dict(AUTO)
        a[u"问"] = u"换了吗?"
        s.write([a, dict(EYE)])
        C.amend(s.ledger, s.cardfile, u"原判据说不清", u"t", s.head())
        return C.effective_verdicts(s.ledger, u"C-t") == []


# ── R7 每条规矩必须有一条会红的用例 ──────────────────────────────────
def r7_red():
    u"""把 R2 的执行器换成恒真 —— 它的必红用例就该不红了,这正是 check 要逮的。"""
    real = C.validate
    C.validate = lambda *a, **k: True
    try:
        return r2_red() is False
    finally:
        C.validate = real


def r7_green():
    u"""不递归调 check:只查册子本身齐不齐(三样缺一,这条规矩不存在)。"""
    R.check_cap()
    here = globals()
    for r in R.RULES:
        if not all(r.get(k) for k in (u"id", u"规矩", u"执行器", u"必红", u"绿对照")):
            return False
        if r[u"必红"] not in here or r[u"绿对照"] not in here:
            return False
    return True


# ── 沉淀那一步(不是规矩,不计入七条)────────────────────────────────
def reflect_red():
    u"""三种该被拦住的:不选、「不写」却不说为什么、「写」却只记事不猜。"""
    return (_red(lambda: J.validate_note({u"by": u"t"}))
            and _red(lambda: J.validate_note({u"by": u"t", u"写不写": u"不写", u"为什么不写": u"没"}))
            and _red(lambda: J.validate_note({u"by": u"t", u"写不写": u"写",
                                              u"事件": {u"what": u"出了一件事"}})))


def reflect_green():
    u"""两条正常的路:老实说不写,以及写一条挂到已有猜测上。"""
    return (J.validate_note({u"by": u"t", u"写不写": u"不写",
                             u"为什么不写": u"这一轮碰到的是上一轮那条的又一次,没有新东西"})
            and J.validate_note({u"by": u"t", u"写不写": u"写",
                                 u"事件": {u"what": u"检查报了错却仍然判过"},
                                 u"挂到": [{u"pattern": u"P280", u"为什么": u"同一个形"}]}))
