# -*- coding: utf-8 -*-
u"""查账本有没有被 git 管起来。

这个工具的全部价值是那本账。账只活在这台机器的硬盘上、而 git 里一行都没有的时候,
**「账好好的」和「账已经没了」在屏幕上逐字同形** —— `done log` 照样打印,
`done verify` 照样说链完好,直到容器被回收那一刻,26 条判决一起消失。

所以这条查的是:账文件在不在 git 的清单里。不查内容,只查它有没有被管。
"""
import os
import subprocess
import sys

账 = os.path.join(u".done", u"ledger.jsonl")


def 被管着(repo, path):
    p = subprocess.run([u"git", u"-C", repo, u"ls-files", u"--error-unmatch", path],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode == 0


def main(argv=None):
    repo = (argv or sys.argv[1:] or [u"."])[0]
    full = os.path.join(repo, 账)
    if not os.path.exists(full):
        sys.stderr.write(u"账文件不在:%s\n" % full)
        return 1
    if not 被管着(repo, 账):
        sys.stderr.write(
            u"账没进 git:%s\n"
            u"  它现在只活在这台机器上。容器一回收,全部判决记录一起没。\n"
            u"  查一下 .gitignore 里是不是把 .done/ 挡掉了。\n" % 账)
        return 1
    n = sum(1 for _ in open(full, encoding=u"utf-8"))
    print(u"账进了 git,%d 条" % n)
    return 0


if __name__ == u"__main__":
    sys.exit(main())
