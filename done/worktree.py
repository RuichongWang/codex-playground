# -*- coding: utf-8 -*-
u"""在某个提交的临时副本里跑命令 —— 只干这一件事。

**判据里的命令是别人写的字,不是你的。** 所以它们永远跑在一棵临时 detached worktree 里,
不在你的工作目录、也不在真仓库上。这条规矩此前有两份副本(`done/judge.py` 一份、
`done/opencheck.py` 一份),而事故恰好出在其中一份:开卡那一步第一版没进 worktree,
`make check` 里那条故意往账里追加垃圾的用例,被它在真仓库根目录上跑了三遍。
**一条规矩有两份副本,就是两份各自会漂的副本。** 收成一份。
"""
import contextlib
import os
import shutil
import subprocess
import tempfile


def 跑(cmd, cwd, timeout=900):
    u"""跑一条命令,回 (退出码, 输出)。超时回 124。"""
    p = subprocess.Popen(cmd, cwd=cwd, shell=True, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    try:
        out = p.communicate(timeout=timeout)[0]
    except subprocess.TimeoutExpired:
        p.kill()
        return 124, u"TIMEOUT"
    return p.returncode, out.decode(u"utf-8", u"replace")


@contextlib.contextmanager
def 临时副本(repo, commit=u"HEAD"):
    u"""把 repo 在 commit 上摊一棵临时 detached worktree,交出它的路径。

    出了这个块一定拆干净 —— 包括中间抛异常的时候。
    起不来就抛 `起不来`,由调用方决定是拒绝还是记一句跳过。
    """
    tmp = tempfile.mkdtemp(prefix=u"done-wt-")
    wt = os.path.join(tmp, u"t")
    rc, out = 跑(u"git worktree add --detach %s %s" % (wt, commit), repo)
    if rc != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        raise 起不来(out.strip()[:300])
    try:
        yield wt
    finally:
        跑(u"git worktree remove --force %s" % wt, repo)
        shutil.rmtree(tmp, ignore_errors=True)


class 起不来(Exception):
    u"""摊不出临时副本(比如这个仓还没有任何提交,或者 commit 解不开)。"""
