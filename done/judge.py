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
    if ans not in (u"是", u"否", u"答不了"):
        raise Refused(u"answer-domain", u"%s 的答要是 是/否/答不了,给的是 %s" % (c[u"id"], ans))
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
        if ln.get(u"判者") == u"读者" and ln.get(u"答") != u"答不了" \
                and not ev.get(u"引文在证据里"):
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
