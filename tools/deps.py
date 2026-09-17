# -*- coding: utf-8 -*-
u"""模块之间的依赖有没有成环 —— 全量扫,没有阈值。

这是「防屎山」里唯一能机械判的那一半:环是客观的,不需要拍一个数字。
另一半(一个文件是不是在同时干好几件事)交给判官答,见卡上那一条。
"""
import ast
import io
import os
import sys

PKG = u"done"


def _imports(path):
    t = ast.parse(io.open(path, encoding=u"utf-8").read())
    out = set()
    for n in ast.walk(t):
        if isinstance(n, ast.ImportFrom) and (n.module or u"").startswith(PKG):
            out.add(n.module.split(u".")[-1])
        elif isinstance(n, ast.Import):
            for a in n.names:
                if a.name.startswith(PKG + u"."):
                    out.add(a.name.split(u".")[-1])
    return out


def main():
    g = {}
    for f in sorted(os.listdir(PKG)):
        if f.endswith(u".py"):
            m = f[:-3]
            g[m] = _imports(os.path.join(PKG, f)) - set([m, u"__init__"])
    环 = []
    def 走(m, 路):
        for d in sorted(g.get(m, ())):
            if d in 路:
                环.append(u" → ".join(路[路.index(d):] + [d]))
            elif d in g:
                走(d, 路 + [d])
    for m in sorted(g):
        走(m, [m])
    print(u"%s/ 里 %d 个模块,%d 条依赖边,环 %d 个"
          % (PKG, len(g), sum(len(v) for v in g.values()), len(环)))
    for c in sorted(set(环)):
        sys.stderr.write(u"成环:%s\n" % c)
    return 1 if 环 else 0


if __name__ == u"__main__":
    sys.exit(main())
