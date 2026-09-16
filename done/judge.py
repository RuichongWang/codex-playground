# -*- coding: utf-8 -*-
u"""判:在一个 detached worktree 里判一个 commit,逐条出结果,不合成总分(R3 · R4 · R5)。

判的对象是**提交**,不是工作区 —— 未提交的改动影响不了判决,判的是哪一版查得到。
auto 那几条命令跑在临时 worktree 里,而账不在那棵树上,所以干活的那只手够不着它(R4)。
"""
import hashlib
import os
import shutil
import subprocess
import tempfile

from done.card import load, registered, spec_hash, validate
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


def _evidence(rc, out):
    return {u"exit": rc, u"out_sha": hashlib.sha256(out.encode(u"utf-8")).hexdigest()[:16],
            u"out_head": out[:200]}


def _met(how, rc, out):
    if how.get(u"stdout_contains"):
        return how[u"stdout_contains"] in out
    exp = how.get(u"期望")
    return rc == 0 if exp == u"exit0" else rc != 0


def _resolve(repo, at):
    rc, out = _sh(u"git rev-parse --verify %s^{commit}" % at, repo)
    if rc != 0:
        raise Refused(u"bad-commit", u"解不开这个 commit:%s" % at)
    return out.strip()


def validate_verdict(body):
    u"""落账之前的最后一道:逐条带 evidence,且不许出现任何合成出来的总分(R5)。"""
    for k in body:
        if k.lower() in 禁合成:
            raise Refused(u"no-aggregate",
                          u"verdict 里出现了 %s —— 逐条清单不合成总分,总分是可以被优化的东西" % k)
    lines = body.get(u"lines")
    if not lines:
        raise Refused(u"verdict-empty", u"verdict 一条结果都没有")
    for ln in lines:
        if not ln.get(u"evidence"):
            raise Refused(u"no-evidence", u"%s 这一条没有 evidence —— 没有 evidence 的判决不许落账"
                          % ln.get(u"id"))
    return True


def judge(ledger_path, card_file, repo, at, chain_head, eye=None):
    card = load(card_file)
    validate(card[u"accept"])
    cur = registered(ledger_path, card[u"id"])
    if cur is None:
        raise Refused(u"card-not-open", u"%s 还没开卡" % card[u"id"])
    sh = spec_hash(card[u"accept"])
    if sh != cur:
        raise Refused(u"accept-drifted",
                      u"accept 跟开卡时冻住的那一份对不上。要改判据走 amend,改完旧 verdict 作废")
    commit = _resolve(repo, at)
    tmp = tempfile.mkdtemp(prefix=u"done-wt-")
    wt = os.path.join(tmp, u"t")
    rc, out = _sh(u"git worktree add --detach %s %s" % (wt, commit), repo)
    if rc != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        raise Refused(u"worktree-failed", out.strip()[:300])
    lines = []
    try:
        for c in card[u"accept"]:
            if c[u"档"] == u"auto":
                rc, out = _sh(c[u"怎么验"][u"cmd"], wt)
                lines.append({u"id": c[u"id"], u"档": u"auto",
                              u"passed": _met(c[u"怎么验"], rc, out),
                              u"evidence": _evidence(rc, out)})
            else:
                e = (eye or {}).get(c[u"id"])
                if not e:
                    d = c[u"靠什么兜"]
                    raise Refused(u"eye-missing",
                                  u"%s 要人判 —— %s 看:%s" % (c[u"id"], d[u"谁"], d[u"看什么"]))
                if not e.get(u"by") or not e.get(u"note"):
                    raise Refused(u"eye-evidence", u"%s 的人判要写清谁判的、看到了什么" % c[u"id"])
                lines.append({u"id": c[u"id"], u"档": u"eye", u"passed": bool(e[u"pass"]),
                              u"evidence": {u"by": e[u"by"], u"note": e[u"note"]}})
    finally:
        _sh(u"git worktree remove --force %s" % wt, repo)
        shutil.rmtree(tmp, ignore_errors=True)
    body = {u"card": card[u"id"], u"commit": commit, u"spec_hash": sh, u"lines": lines,
            u"passed": all(l[u"passed"] for l in lines)}
    validate_verdict(body)
    return append(ledger_path, u"verdict", body, chain_head)
