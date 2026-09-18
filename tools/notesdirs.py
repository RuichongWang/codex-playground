# -*- coding: utf-8 -*-
u"""`pattern/NOTES.md` 那块目录树,对着盘上实际的目录核一遍。

**为什么要有这个。** 这个仓栽在「手抄的东西慢慢跟实际对不上」上已经不止四轮了,
而每一次都是**人偶然撞见**的,没有一道检查看着。这一块自己就漂了两处:
技能目录写成相对 `pattern/`(它在仓库根上),`ph/` 整个包一行都没提。

管两头:
  多列了   —— 列表里写着的目录盘上没有(改名 / 删掉了,说明书没跟)
  少列了   —— 盘上有的顶层目录列表里没有(新加的包,说明书没跟)

`<仓库根>/` 开头的那几行按仓库根解,其余按 `pattern/` 解;写了 `*` 的按通配解,**没写 `*` 的一律逐字比** —— 拿前缀去凑等于给自己开后门。
带 `__` 开头的、隐藏的、以及 `.claude` 这类不是这个库自己的东西不算漏。
"""
import fnmatch
import glob
import io
import os
import re
import sys

默认根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
围栏 = re.compile(u"## 目录\n.*?```\n(.*?)```", re.S)
不算 = (u"__pycache__",)


def 列着的(块):
    for 行 in 块.splitlines():
        名 = 行.split()[0] if 行.strip() else u""
        if 名.endswith(u"/"):
            yield 名


def main(argv=None):
    根 = (argv or sys.argv[1:] or [默认根])[0]
    笔记 = os.path.join(根, u"pattern", u"NOTES.md")
    if not os.path.exists(笔记):
        print(u"没有 pattern/NOTES.md,跳过")
        return 0
    m = 围栏.search(io.open(笔记, encoding=u"utf-8").read())
    if not m:
        sys.stderr.write(u"pattern/NOTES.md 里找不到「## 目录」那一块\n")
        return 1
    列 = list(列着的(m.group(1)))
    坏 = []
    自家 = set()
    for 名 in 列:
        if 名.startswith(u"<仓库根>/"):
            p = os.path.join(根, 名[len(u"<仓库根>/"):])
        else:
            p = os.path.join(根, u"pattern", 名)
            自家.add(名.rstrip(u"/").split(u"/")[0])
        # 只有**真写了 `*`** 的那一条才按通配解。上一版是拿 `rstrip("*")` 当前缀比,
        # 于是 `corpus/` 这条(没有星号)也成了前缀,`pattern/corpus4/` 新建出来
        # 一声不吭地就过了 —— 而这块目录树里根本没有一条带星号,那条豁免从头到尾
        # 只在放行本该逮住的东西。同时笔记里写着「少列一个它就红」,那句话因此是假的。
        if u"*" in 名:
            if not any(os.path.isdir(x) for x in glob.glob(p)):
                坏.append(u"列着 %s,盘上一个都对不上" % 名)
        elif not os.path.isdir(p):
            坏.append(u"列着 %s,盘上没有这个目录" % 名)
    盘上 = set(d for d in os.listdir(os.path.join(根, u"pattern"))
              if os.path.isdir(os.path.join(根, u"pattern", d))
              and not d.startswith(u".") and d not in 不算)
    通配 = [x for x in 自家 if u"*" in x]
    for d in sorted(盘上 - 自家):
        if not any(fnmatch.fnmatch(d, x) for x in 通配):
            坏.append(u"盘上有 pattern/%s/,列表里没提 —— 说明书没跟上" % d)
    for b in 坏:
        sys.stderr.write(u"%s\n" % b)
    print(u"NOTES.md 目录树列了 %d 条,跟盘上对不上的 %d 条" % (len(列), len(坏)))
    return 1 if 坏 else 0


if __name__ == u"__main__":
    sys.exit(main())
