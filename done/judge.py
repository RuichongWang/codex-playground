# -*- coding: utf-8 -*-
u"""判:在 detached worktree 里判一个 commit,逐条出结果,不合成总分(R3 · R4 · R5)。

判的对象是**提交**不是工作区,auto 那几条命令跑在临时树里,而账不在那棵树上(R4)。
读者那一档要交一份报告,**引文必须是它自己给的证据的逐字子串** —— 于是
「判官照没照判据答」是机械可查的,人只剩「这条判据是不是在要求形成看法」一件事。
"""
import hashlib
import os
import shutil
import subprocess
import tempfile

from done.card import accept_of, load, registered, spec_hash
from done.ledger import Refused, append

禁合成 = (u"score", u"总分", u"percent", u"百分比", u"weight", u"加权")


def _sh(cmd, cwd, timeout=900):
    p = subprocess.Popen(cmd, cwd=cwd, shell=True, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    try:
        out = p.communicate(timeout=timeout)[0]
    except subprocess.TimeoutExpired:
        p.kill()
        return 124, u"TIMEOUT"
    return p.returncode, out.decode(u"utf-8", u"replace")


def _sha(s):
    return hashlib.sha256(s.encode(u"utf-8")).hexdigest()[:16]


def _cmd_answer(j, rc, out):
    if j.get(u"stdout_contains"):
        return u"是" if j[u"stdout_contains"] in out else u"否"
    return u"否" if (rc != 0) == (j.get(u"答是", u"exit0") == u"exit0") else u"是"


def _reader_line(c, rep):
    a = (rep or {}).get(c[u"id"])
    if not a:
        raise Refused(u"reader-missing", u"%s 要「%s」来判 —— 问的是:%s(凭 %s)"
                      % (c[u"id"], c[u"判者"][u"读者"], c[u"问"], c[u"凭什么答"]))
    ans, q, e = a.get(u"答"), a.get(u"引文") or u"", a.get(u"证据") or u""
    找 = c[u"过"] == u"没找到"
    域 = (u"找到", u"没找到", u"答不了") if 找 else (u"是", u"否", u"答不了")
    if ans not in 域:
        raise Refused(u"answer-domain", u"%s 的答要是 %s,给的是 %s"
                      % (c[u"id"], u"/".join(域), ans))
    if 找 and ans == u"没找到":
        # **没找到不等于没有。**所以这一格不收「证据」,收的是「你搜了什么」——
        # 让这一轮花没花力气留在明处,人抽查的时候看的就是它。
        搜 = (a.get(u"搜了什么") or u"").strip()
        if len(搜) < 10:
            raise Refused(u"no-search",
                          u"%s 答「没找到」要写清你搜了什么 —— 没找到不等于没有" % c[u"id"])
        return {u"搜了什么": 搜[:300], u"judge": a.get(u"judge", u""),
                u"注": u"没找到 ≠ 没有,只是这一轮没逮着"}
    inside = bool(q) and q in e
    if ans != u"答不了" and not inside:
        raise Refused(u"quote-not-in-evidence",
                      u"%s 的引文不在它自己给的证据里 —— 引文必须逐字截取,不许改写" % c[u"id"])
    return {u"引文": q[:200], u"证据sha": _sha(e), u"证据长": len(e),
            u"引文在证据里": inside, u"judge": a.get(u"judge", u"")}


def _resolve(repo, at):
    rc, out = _sh(u"git rev-parse --verify %s^{commit}" % at, repo)
    if rc != 0:
        raise Refused(u"bad-commit", u"解不开这个 commit:%s" % at)
    return out.strip()


def validate_verdict(body):
    u"""落账之前的最后一道(R5):逐条带 evidence · 引文对得上 · 不许有合成出来的总分。"""
    for k in body:
        if k.lower() in 禁合成:
            raise Refused(u"no-aggregate",
                          u"verdict 里出现了 %s —— 逐条清单不合成总分,总分是可以被优化的东西" % k)
    lines = body.get(u"lines")
    if not lines:
        raise Refused(u"verdict-empty", u"verdict 一条结果都没有")
    for ln in lines:
        ev = ln.get(u"evidence")
        if not ev:
            raise Refused(u"no-evidence", u"%s 没有 evidence —— 没有 evidence 的判决不许落账"
                          % ln.get(u"id"))
        if ln.get(u"判者") == u"cmd" or ln.get(u"答") == u"答不了":
            continue
        if ln.get(u"答") == u"没找到":
            if not ev.get(u"搜了什么"):
                raise Refused(u"no-search",
                              u"%s 答「没找到」却没写搜了什么 —— 那是个免费答案" % ln.get(u"id"))
        elif not ev.get(u"引文在证据里"):
            raise Refused(u"quote-not-in-evidence",
                          u"%s 的引文不在证据里 —— 这一条不算答过" % ln.get(u"id"))
    return True


def judge(ledger_path, card_file, repo, at, chain_head, reports=None, packs=u"packs"):
    card = load(card_file)
    accept = accept_of(card_file, packs)
    cur = registered(ledger_path, card[u"id"])
    if cur is None:
        raise Refused(u"card-not-open", u"%s 还没开卡" % card[u"id"])
    sh = spec_hash(accept)
    if sh != cur:
        raise Refused(u"accept-drifted",
                      u"判据跟开卡时冻住的那一份对不上。要改走 amend,改完旧 verdict 作废")
    commit = _resolve(repo, at)
    tmp = tempfile.mkdtemp(prefix=u"done-wt-")
    wt = os.path.join(tmp, u"t")
    rc, out = _sh(u"git worktree add --detach %s %s" % (wt, commit), repo)
    if rc != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        raise Refused(u"worktree-failed", out.strip()[:300])
    lines = []
    try:
        for c in accept:
            j = c[u"判者"]
            if isinstance(j, dict) and j.get(u"cmd"):
                rc, out = _sh(j[u"cmd"], wt)
                ans = _cmd_answer(j, rc, out)
                ev = {u"exit": rc, u"out_sha": _sha(out), u"out_head": out[:200]}
                who = u"cmd"
            else:
                ans = (reports or {}).get(c[u"id"], {}).get(u"答")
                ev = _reader_line(c, reports)
                who = j[u"读者"]
            lines.append({u"id": c[u"id"], u"判者": who, u"答": ans,
                          u"passed": ans == c[u"过"], u"evidence": ev})
    finally:
        _sh(u"git worktree remove --force %s" % wt, repo)
        shutil.rmtree(tmp, ignore_errors=True)
    body = {u"card": card[u"id"], u"commit": commit, u"spec_hash": sh, u"lines": lines,
            u"答不了": [l[u"id"] for l in lines if l[u"答"] == u"答不了"],
            u"passed": all(l[u"passed"] for l in lines)}
    validate_verdict(body)
    return append(ledger_path, u"verdict", body, chain_head)


def reflect(ledger_path, card_file, chain_head, note):
    u"""卡判完之后的一步:由一个 agent 看完这一轮,**自己决定要不要往库里写**。

    **「不写」是正常结果,不是失败** —— 绝大多数轮次本来就没什么值得记的,
    自动沉淀只会把库灌满废话。但「不写」必须落账并写明理由:
    一个正确的零和一次根本没跑过,在盘面上完全同形。

    这一步**不产生 done**,所以它不占规矩位;真正写进库的动作归 pattern 那一侧。
    """
    card = load(card_file)
    cid = card[u"id"]
    if not [r for r in read(ledger_path)
            if r.get(u"kind") == u"verdict" and (r.get(u"body") or {}).get(u"card") == cid]:
        raise Refused(u"no-verdict", u"%s 还没判过,没什么可沉淀的" % cid)
    validate_note(note)
    body = dict(note)
    body[u"card"] = cid
    return append(ledger_path, u"reflect", body, chain_head)


def validate_note(n):
    u"""沉淀报告的形状。写与不写二选一,两边各自要交的东西不同。"""
    if not (n or {}).get(u"by"):
        raise Refused(u"reflect-by", u"沉淀报告要写明是谁做的")
    w = (n or {}).get(u"写不写")
    if w not in (u"写", u"不写"):
        raise Refused(u"reflect-choice", u"「写不写」要么「写」要么「不写」")
    if w == u"不写":
        why = (n.get(u"为什么不写") or u"").strip()
        if len(why) < 10:
            raise Refused(u"reflect-why",
                          u"「不写」也要写明为什么 —— 一个正确的零和一次没跑过,盘面上同形")
        return True
    if not ((n.get(u"事件") or {}).get(u"what") or u"").strip():
        raise Refused(u"reflect-what", u"要写就得有一件具体的事:发生了什么")
    if not (n.get(u"挂到") or n.get(u"新猜测")):
        raise Refused(u"reflect-link",
                      u"要么挂到库里已有的猜测上,要么提一条新的 —— 只记事不猜,库长不起来")
    return True
