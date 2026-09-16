# -*- coding: utf-8 -*-
u"""把 README 里每条 done 命令喂给工具,看它认不认得出来。

只判「命令长得对不对」(参数名、子命令),不判它跑不跑得成 —— 后者要动真账。
`--eye` 那种「说明书写了一个根本不存在的参数」正好落在这一层,而它连着坑了两轮。
"""
import io
import os
import shlex
import subprocess
import sys
import tempfile

坏 = (u"unrecognized arguments", u"invalid choice", u"usage: done")


def 抽命令(text):
    u"""**跨行的要接起来**:行尾一个反斜杠就是下一行还是它 —— 漏接的话,
    后半截里的参数一个都进不了检查(第一版就栽在这儿,`--eye` 正好写在后半截)。"""
    out, inblock, buf = [], False, None
    for line in text.splitlines():
        if line.strip().startswith(u"```"):
            inblock = not inblock
            buf = None
            continue
        if not inblock:
            continue
        s = line.strip()
        if buf is not None:
            buf += u" " + s.rstrip(u"\\").strip()
            if not s.endswith(u"\\"):
                out.append(buf)
                buf = None
            continue
        if s.startswith(u"python3 -m done.cli"):
            if s.endswith(u"\\"):
                buf = s.rstrip(u"\\").strip()
            else:
                out.append(s)
    return out


def main():
    text = io.open(u"README.md", encoding=u"utf-8").read()
    cmds = 抽命令(text)
    if not cmds:
        print(u"README 里一条 done 命令都没有 —— 说明书该有例子")
        return 1
    tmp = tempfile.mkdtemp(prefix=u"readme-")
    bad = []
    for c in cmds:
        argv = shlex.split(c, comments=True)[3:]   # 行尾的 # 注释不算参数
        p = subprocess.Popen([sys.executable, u"-m", u"done.cli",
                              u"--ledger", os.path.join(tmp, u"l.jsonl")] + argv,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        err = p.communicate()[1].decode(u"utf-8", u"replace")
        if any(k in err for k in 坏):
            bad.append((c, err.strip().splitlines()[-1]))
    for c, e in bad:
        sys.stderr.write(u"说明书这条命令工具不认:\n  %s\n  → %s\n" % (c, e))
    print(u"README 里 %d 条 done 命令,认不出的 %d 条" % (len(cmds), len(bad)))
    return 1 if bad else 0


if __name__ == u"__main__":
    sys.exit(main())
