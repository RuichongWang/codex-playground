# -*- coding: utf-8 -*-
u"""记忆库的订正通道 —— 改得动,但每一处都要过一次**纯模型评审**。

**为什么要有这条路**:库原来只有「写进去」。第一次真用它,审阅人就逐条指出措辞没翻干净、
几条结局站不住,而没有任何通道可以改 —— 只能直接改底层文件,谁也拦不住。

**为什么评审是「模型」不是「agent」**:agent 能去翻仓库、能形成自己的看法,于是它会
顺着订正者的意思走。这里要的是一个**只看三样东西**的读者:改前、改后、为什么。
它只答三问,任何一条不合格就不许写:

  一、改完之后,这条还是在说同一件事吗?
  二、这次是**只改了措辞或事实错误**,还是偷偷加强/削弱了这条主张?
  三、有没有把一条具体的事实,换成一句更好听但更空的话?

**这个文件只管规矩那一半**:一份订正 + 一份评审摆在面前,准不准写进库。
评审是怎么问出来的在隔壁 `tools/puremodel.py` —— 也可以不问,
把评审记录当文件交进来(`--评审`),两条路产出的记录一模一样。
**那一段整个拿掉,这儿一行都不用动**,所以它不在这儿。
"""
import io
import json
import os
import sys

from tools.puremodel import 评审 as 问一轮
from tools.puremodel import 问不出来

DB = os.path.join(u"pattern", u"runs", u"r3", u"library.json")
LOG = os.path.join(u"pattern", u"docs", u"corrections.jsonl")
三问 = [u"改完之后这条还是在说同一件事吗", u"是不是只改了措辞或事实错误(没有加强或削弱这条主张)",
        u"有没有把一条具体的事实换成一句更空的话(有=不合格)"]


class 拒(Exception):
    pass


def 校(提案, 评审, nodes):
    u"""写之前的全部关卡。任何一条不过,整批都不写。"""
    if not 提案:
        raise 拒(u"提案是空的")
    r = {x[u"序号"]: x for x in (评审 or {}).get(u"逐条", [])}
    if not (评审 or {}).get(u"评审者"):
        raise 拒(u"评审记录要写明是谁评的(哪个模型、哪一次调用)")
    for i, p in enumerate(提案):
        for k in (u"节点", u"栏", u"改前", u"改后", u"为什么"):
            if not p.get(k):
                raise 拒(u"第 %d 条缺「%s」" % (i, k))
        n = nodes.get(p[u"节点"])
        if n is None:
            raise 拒(u"第 %d 条:库里没有 %s" % (i, p[u"节点"]))
        if n.get(p[u"栏"]) != p[u"改前"]:
            raise 拒(u"第 %d 条:「改前」跟库里现在的值对不上 —— 你手上那份是旧的" % i)
        v = r.get(i)
        if not v:
            raise 拒(u"第 %d 条没有评审" % i)
        if set(v.get(u"三问", {}).keys()) != set(三问):
            raise 拒(u"第 %d 条的评审没把三问答全" % i)
        if not v.get(u"通过"):
            raise 拒(u"第 %d 条评审没过:%s" % (i, v.get(u"理由", u"")))
    return True


def main(argv=None):
    a = dict(zip(sys.argv[1::2], sys.argv[2::2]))
    if u"--提案" not in a:
        sys.stderr.write(u"用法:correct.py --提案 <json> [--评审 <json>]\n")
        return 2
    提案 = json.loads(io.open(a[u"--提案"], encoding=u"utf-8").read())
    评 = json.loads(io.open(a[u"--评审"], encoding=u"utf-8").read()) if a.get(u"--评审") else 问一轮(提案, 三问)
    d = json.loads(io.open(DB, encoding=u"utf-8").read())
    校(提案, 评, d[u"nodes"])
    for p in 提案:
        d[u"nodes"][p[u"节点"]][p[u"栏"]] = p[u"改后"]
    io.open(DB, u"w", encoding=u"utf-8").write(json.dumps(d, ensure_ascii=False))
    with io.open(LOG, u"a", encoding=u"utf-8") as f:
        f.write(json.dumps({u"提案": 提案, u"评审": 评}, ensure_ascii=False) + u"\n")
    print(u"订正 %d 处,评审者 %s,已追加进 %s" % (len(提案), 评[u"评审者"], LOG))
    return 0


if __name__ == u"__main__":
    try:
        sys.exit(main())
    except (拒, 问不出来) as e:
        sys.stderr.write(u"拒绝:%s\n" % e)
        sys.exit(1)
