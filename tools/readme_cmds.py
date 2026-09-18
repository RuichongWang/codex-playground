# -*- coding: utf-8 -*-
u"""说明书里印出来的命令,今天还立得住吗。

两种命令各查一层,**两层都进退出码**:

  `python3 -m done.cli …`   参数名、子命令,工具认不认得出
  `python3 tools/xxx.py …`  照说明书那样**当脚本跑**的时候,它起不起得来

`--eye` 那种「说明书写了一个根本不存在的参数」正好落在第一层,而它连着坑了两轮。

**第二层是被打脸打出来的。** 有一次往 `tools/correct.py` 顶上加了一行
`from tools.puremodel import …`,而说明书教人跑的是 `python3 tools/correct.py …` ——
当脚本跑的时候 Python 只把 `tools/` 放进搜索路径、仓库根不在,于是一开口就崩。
盘上当时没有任何东西发现:那条会报错的例子走的是 `from tools import correct`
(从仓库根导入,进得去),说明书让人走的是脚本那条路,**两条根本不是同一条**;
而这个文件那时只收 `python3 -m done.cli` 开头的行,脚本那条路不在名单里。
所以第二层**照脚本的方式起**(把脚本所在目录放进 sys.path[0],和 `python3 tools/x.py`
逐字同构),而不是 import 一下就算数 —— 后者正是当初漏掉它的那个姿势。

只判「起不起得来 / 长得对不对」,不判它跑不跑得成 —— 后者要动真账、要联网。
所以第二层只跑模块体,不跑 `main()`。
"""
import io
import os
import re
import shlex
import subprocess
import sys
import tempfile

坏话 = (u"unrecognized arguments", u"invalid choice", u"usage: done")


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


脚本 = re.compile(u"python3 (tools/[A-Za-z0-9_]+\\.py)")
起不来 = u"Traceback"


def 抽脚本(text):
    u"""全篇找,**不限代码块** —— 说明书正文里随手写的一条命令一样会被人贴进终端。"""
    out = []
    for m in 脚本.finditer(text):
        if m.group(1) not in out:
            out.append(m.group(1))
    return out


def 查命令(cmds, 账目录):
    坏 = []
    for c in cmds:
        argv = shlex.split(c, comments=True)[3:]   # 行尾的 # 注释不算参数
        p = subprocess.Popen([sys.executable, u"-m", u"done.cli",
                              u"--ledger", os.path.join(账目录, u"l.jsonl")] + argv,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        err = p.communicate()[1].decode(u"utf-8", u"replace")
        if any(k in err for k in 坏话):
            坏.append((c, err.strip().splitlines()[-1]))
    return 坏


def 查脚本(名单, 根=u"."):
    u"""照 `python3 tools/x.py` 的姿势把每个脚本起一遍:只跑模块体,不跑 main()。

    `run_name` 故意不是 `__main__`,所以 `if __name__ == u"__main__"` 那一段不会执行 ——
    这些脚本里有改库、要联网的,自检不该真去干那件事。崩在 import 上就崩在模块体里,
    照样逮得到。
    """
    坏 = []
    for 名 in 名单:
        探 = (u"import sys, runpy\n"
              u"sys.path.insert(0, %r)\n"
              u"runpy.run_path(%r, run_name='__说明书自检__')\n"
              % (os.path.join(根, os.path.dirname(名)), os.path.join(根, 名)))
        # **`-P` 不能省。** 少了它,`python3 -c` 会把当前目录塞进 sys.path[0],
        # 于是 `import tools` 从仓库根跑起来就通了 —— 而 `python3 tools/x.py` 里
        # sys.path[0] 是 `tools/`,仓库根不在。那正是当初漏掉这件事的姿势,
        # 拿它来自检等于自检也一起漏。
        p = subprocess.Popen([sys.executable, u"-P", u"-c", 探], cwd=根,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        err = p.communicate()[1].decode(u"utf-8", u"replace")
        if 起不来 in err:
            坏.append((名, err.strip().splitlines()[-1]))
    return 坏


def main():
    text = io.open(u"README.md", encoding=u"utf-8").read()
    cmds = 抽命令(text)
    if not cmds:
        print(u"README 里一条 done 命令都没有 —— 说明书该有例子")
        return 1
    坏1 = 查命令(cmds, tempfile.mkdtemp(prefix=u"readme-"))
    名单 = 抽脚本(text)
    坏2 = 查脚本(名单)
    for c, e in 坏1:
        sys.stderr.write(u"说明书这条命令工具不认:\n  %s\n  → %s\n" % (c, e))
    for c, e in 坏2:
        sys.stderr.write(u"说明书教人跑 python3 %s,当脚本跑起不来:\n  → %s\n" % (c, e))
    print(u"README 里 %d 条 done 命令,认不出的 %d 条;%d 个脚本命令,起不来的 %d 个"
          % (len(cmds), len(坏1), len(名单), len(坏2)))
    return 1 if (坏1 or 坏2) else 0


if __name__ == u"__main__":
    sys.exit(main())
