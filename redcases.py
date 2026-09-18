# -*- coding: utf-8 -*-
u"""必红用例与绿对照。每条规矩一红一绿,缺一条这条规矩就不存在。

约定:必红用例返回 True = 「它确实红了」;绿对照返回 True = 「正常那条路走通了」。
"""
import contextlib
import io as _io
import json
import os
import shutil
import subprocess
import tempfile

from done import card as C
from done import judge as J
from done import ledger as L
from done import reflect as RF
from done import rules as R
from tools import doc_cards as DC
from tools import ledgerkept as LK

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
    return (_red(lambda: RF.validate_note({u"by": u"t"}))
            and _red(lambda: RF.validate_note({u"by": u"t", u"写不写": u"不写", u"为什么不写": u"没"}))
            and _red(lambda: RF.validate_note({u"by": u"t", u"写不写": u"写",
                                              u"事件": {u"what": u"出了一件事"}})))


def reflect_green():
    u"""三条正常的路 —— 最后那条**真的走一遍 reflect 本身**。

    头两条只验形状。上一版只有它们,于是 `reflect` 里一个没导入的名字整条路都没人走过,
    第一次真跑当场崩 —— 那正是本轮沉淀提出的那条猜测:一道为某次失败新建的检查,
    进表用的是整类失败的名字,实际只覆盖那一次已经显形的形状。
    """
    with Sandbox() as s:
        _open(s)
        _judge(s)
        row = RF.reflect(s.ledger, s.cardfile, s.head(),
                        {u"by": u"t", u"写不写": u"不写",
                         u"为什么不写": u"这一轮没有新东西,是上一轮那条的又一次"})
        if row[u"kind"] != u"reflect":
            return False
        # 没判过的卡不许沉淀
        with Sandbox() as s2:
            _open(s2)
            if not _red(lambda: RF.reflect(s2.ledger, s2.cardfile, s2.head(),
                                          {u"by": u"t", u"写不写": u"不写",
                                           u"为什么不写": u"还没判过就想沉淀"})):
                return False
    return (RF.validate_note({u"by": u"t", u"写不写": u"不写",
                             u"为什么不写": u"这一轮碰到的是上一轮那条的又一次,没有新东西"})
            and RF.validate_note({u"by": u"t", u"写不写": u"写",
                                 u"事件": {u"what": u"检查报了错却仍然判过"},
                                 u"挂到": [{u"pattern": u"P280", u"为什么": u"同一个形"}]}))


# ── 记忆库的订正通道(不是规矩,不计入七条)──────────────────────────
# 以前这里是按相对路径 tools/correct.py 加载的 —— 那等于把「必红用例跑不跑得起来」
# 绑死在「你人在仓库根目录」上,换个工作目录就是 FileNotFoundError。现在 tools 是个包,
# 直接 import。
from tools import correct as CO

_库 = {u"I1": {u"kind": u"item", u"what": u"原来那句话"}}
_好提案 = [{u"节点": u"I1", u"栏": u"what", u"改前": u"原来那句话", u"改后": u"原来那一句话",
           u"为什么": u"少一个字,读起来卡"}]
_好评审 = {u"评审者": u"测试", u"逐条": [{u"序号": 0, u"通过": True, u"理由": u"只动措辞",
                                     u"三问": dict((q, u"合格") for q in CO.三问)}]}


def _红(fn):
    try:
        fn()
    except CO.拒:
        return True
    return False


def correct_red():
    u"""四种该被拦住的:没评审 · 评审没过 · 三问没答全 · 「改前」跟库里对不上。"""
    差评 = {u"评审者": u"测试", u"逐条": [dict(_好评审[u"逐条"][0], 通过=False, 理由=u"加强了主张")]}
    缺问 = {u"评审者": u"测试", u"逐条": [dict(_好评审[u"逐条"][0], 三问={CO.三问[0]: u"合格"})]}
    旧本 = [dict(_好提案[0], 改前=u"我手上那份旧的")]
    return (_红(lambda: CO.校(_好提案, {u"评审者": u"测试", u"逐条": []}, _库))
            and _红(lambda: CO.校(_好提案, 差评, _库))
            and _红(lambda: CO.校(_好提案, 缺问, _库))
            and _红(lambda: CO.校(旧本, _好评审, _库)))


def correct_green():
    u"""一份合格的提案 + 一份三问全合格的评审,过。"""
    return CO.校(_好提案, _好评审, _库)


# —— 账要活得下来(不是规矩,单独跑) ——
# 这条不占规矩位:它不决定一件活算不算完成,它决定「完成过什么」这件事明天还在不在。

def _临时仓(挡掉账):
    d = tempfile.mkdtemp()
    subprocess.run([u"git", u"-C", d, u"init", u"-q"], check=True)
    os.makedirs(os.path.join(d, u".done"))
    with open(os.path.join(d, u".done", u"ledger.jsonl"), u"w", encoding=u"utf-8") as f:
        f.write(u'{"kind":"open"}\n')
    if 挡掉账:
        with open(os.path.join(d, u".gitignore"), u"w", encoding=u"utf-8") as f:
            f.write(u".done/\n")
    else:
        subprocess.run([u"git", u"-C", d, u"add", u".done/ledger.jsonl"], check=True)
    return d


def ledger_red():
    u"""账被 .gitignore 挡在外面 —— 屏幕上一切正常,容器一回收就全没了。"""
    d = _临时仓(挡掉账=True)
    try:
        with contextlib.redirect_stderr(_io.StringIO()):
            return LK.main([d]) != 0
    finally:
        shutil.rmtree(d, ignore_errors=True)


def ledger_green():
    u"""账进了 git,过。"""
    d = _临时仓(挡掉账=False)
    try:
        with contextlib.redirect_stdout(_io.StringIO()):
            return LK.main([d]) == 0
    finally:
        shutil.rmtree(d, ignore_errors=True)


# —— 说明书里的判据范例要能真开卡(不是规矩,单独跑) ——
# 第三次栽在同一个跟头上之后加的:设计文档教的写法,拿去开卡当场被拒。

_范例 = (u"照着抄一张卡:\n\n```json\n"
        u'{"id":"x","问":"跑得通吗?","过":"是","判者":%s,"凭什么答":"退出码"}\n'
        u"```\n")


def _临时说明书(判者):
    d = tempfile.mkdtemp(prefix=u"doc-t-")
    with _io.open(os.path.join(d, u"README.md"), u"w", encoding=u"utf-8") as f:
        f.write(_范例 % 判者)
    return d


def doccards_red():
    u"""说明书里写着老写法 `"判者":"读者"` —— 照抄开卡会被拒,得在这儿先红。"""
    d = _临时说明书(u'"读者"')
    try:
        with contextlib.redirect_stderr(_io.StringIO()), \
                contextlib.redirect_stdout(_io.StringIO()):
            return DC.main([d]) != 0
    finally:
        shutil.rmtree(d, ignore_errors=True)


def doccards_green():
    u"""写明是哪一个读者,过。"""
    d = _临时说明书(u'{"读者":"冷读者"}')
    try:
        with contextlib.redirect_stdout(_io.StringIO()):
            return DC.main([d]) == 0
    finally:
        shutil.rmtree(d, ignore_errors=True)


# —— 开卡那一刻的体检(不是规矩,单独跑) ——
# 账上改过 14 次判据,12 次是判据自己写坏了。这几种能在开卡那一刻看出来。

def opencheck_red():
    u"""五种写坏的判据 + 两种写坏的查库记录,一个都不许漏。"""
    from done import opencheck as OC
    好 = {u"id": u"g1", u"问": u"跑得通吗?", u"过": u"是",
         u"判者": {u"cmd": u"true", u"答是": u"exit0"}, u"凭什么答": u"退出码"}
    坏 = [
        {u"id": u"b1", u"问": u"找出一处环", u"过": u"是",
         u"判者": {u"cmd": u"true"}, u"凭什么答": u"输出"},
        {u"id": u"b2", u"问": u"退出码是 0 吗?", u"过": u"没找到",
         u"判者": {u"cmd": u"true"}, u"凭什么答": u"输出"},
        {u"id": u"b3", u"问": u"这次改得怎么样", u"过": u"是",
         u"判者": {u"cmd": u"true"}, u"凭什么答": u"输出"},
        {u"id": u"b4", u"问": u"找出一句假话", u"过": u"没找到",
         u"判者": {u"读者": u"说明书审阅人"}, u"凭什么答": u"README.md 全篇"},
        {u"id": u"b5", u"问": u"找出一处改动没跟上的", u"过": u"没找到",
         u"判者": {u"读者": u"改动审阅人"},
         u"凭什么答": u"库里那几条条目的原文;答「没找到」就写清比了哪几条"},
    ]
    for c in 坏:
        if not OC.查判据([好, c]):
            return False
    return bool(OC.查查库({u"查了什么": u"搜过", u"自造的栏": 1, u"用上了": u"有"})) \
        and bool(OC.查查库({u"查了什么": u"搜过"}))


def opencheck_green():
    u"""两件事:盘上现有的每一张卡都得放行;开卡时跑命令不许碰到工作目录。

    第一半对的是「收紧一道校验,风险落在没人写下来的老用法上」。
    第二半对的是一次真事故:开卡那一步第一版把判据里的命令跑在了**真的工作目录**里,
    而 `make check` 里有一条故意的用例内容正是「往账里追加一行垃圾」——
    于是跑一次开机自检就把真账写坏一行,连着三次没人发现。
    **判据里的命令是别人写的字**,得跟判那一步一样关进 worktree。
    """
    import glob
    import json as _j
    from done import opencheck as OC
    for f in glob.glob(os.path.join(u"cards", u"*.json")):
        c = _j.loads(_io.open(f, encoding=u"utf-8").read())
        if OC.查判据(c.get(u"accept") or []):
            return False
    if OC.查查库({u"查了什么": u"搜过", u"用上了": u"没有,都不对路"}):
        return False
    with Sandbox() as s:
        破坏 = dict(AUTO)
        破坏[u"判者"] = {u"cmd": u"echo x > 我不该出现", u"答是": u"exit0"}
        s.write([破坏, dict(EYE)])
        C.open_card(s.ledger, s.cardfile, u"t", s.head(), repo=s.repo)
        # 两处都要看:**出事那次脏的是当前工作目录**(开卡那一步没带 cwd),
        # 只盯着临时仓看的话,这条用例在 bug 放回去之后照样是绿的 —— 试过,真是绿的。
        for d in (os.getcwd(), s.repo):
            f = os.path.join(d, u"我不该出现")
            if os.path.exists(f):
                os.remove(f)
                return False
        return True
