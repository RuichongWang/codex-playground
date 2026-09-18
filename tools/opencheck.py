# -*- coding: utf-8 -*-
u"""跑开卡体检:对盘上每一张真卡放行,对每一种它声称拦得住的毛病各拦下一张坏样卡。

两件事各答一半:
- **对真卡全绿** —— 收紧一道校验,风险从来不落在你改的那一处,而落在某个从没写下来的
  老用法上(库里 P106)。所以这道检查加进去的同时,得当场证明它没误伤盘上任何一张卡。
- **对坏样卡全红** —— 一条永远不红的检查证明不了自己还活着。这里每种毛病配一张坏样卡,
  而且要求它**恰好被对应那一条**拦下,不是随便红一下就算。

用法:
    python3 tools/opencheck.py --self      对盘上真卡 + 内置坏样卡各跑一遍
    python3 tools/opencheck.py 某张卡.json  单查一张卡
"""
import glob
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from done.opencheck import 查查库, 查判据  # noqa: E402

好命令 = {u"id": u"g1", u"问": u"跑得通吗?", u"过": u"是",
         u"判者": {u"cmd": u"true", u"答是": u"exit0"}, u"凭什么答": u"退出码"}

# 每一项:这种毛病叫什么 · 一张犯了它的坏样卡 · 拦它那句话里必有的字眼 · 它对应账上哪一次
坏样 = [
    (u"问句和「过」对不上(找反例却写「是」)",
     [好命令, {u"id": u"b1", u"问": u"找出一处循环依赖", u"过": u"是",
              u"判者": {u"cmd": u"true", u"答是": u"exit0"}, u"凭什么答": u"输出"}],
     u"「过」只能是「没找到」", u"第 3 次:问句改了「过」没跟着改"),
    (u"问句和「过」对不上(是非问却写「没找到」)",
     [好命令, {u"id": u"b2", u"问": u"退出码是 0 吗?", u"过": u"没找到",
              u"判者": {u"cmd": u"true", u"答是": u"exit0"}, u"凭什么答": u"输出"}],
     u"只能是「是」或「否」", u"第 3 次:同一处的另一半"),
    (u"答域不明(既不是找反例也不是是非问)",
     [好命令, {u"id": u"b3", u"问": u"这次改得怎么样", u"过": u"是",
              u"判者": {u"cmd": u"true", u"答是": u"exit0"}, u"凭什么答": u"输出"}],
     u"答域不明", u"第 8 次:免费答案是从答域没定死开始的"),
    (u"人来答的找反例判据,没交代怎么算搜过",
     [好命令, {u"id": u"b4", u"问": u"找出一句假话", u"过": u"没找到",
              u"判者": {u"读者": u"说明书审阅人"}, u"凭什么答": u"README.md 全篇"}],
     u"答没找到就写清什么", u"第 8 次:「没找到」不写搜了什么就是免费答案"),
    (u"审阅人的名字和给他的取材对不上",
     [好命令, {u"id": u"b5", u"问": u"找出一处改动没跟上的地方", u"过": u"没找到",
              u"判者": {u"读者": u"改动审阅人"},
              u"凭什么答": u"库里那几条条目的原文;答「没找到」就写清你比了哪几条"}],
     u"名字和取材对不上", u"第 7 · 10 次:判者名不副实,他结构上答不了"),
]

坏查库 = [
    (u"查库那一栏自造栏名",
     {u"查了什么": u"搜了入口那几条", u"怎么用的": u"照它改了范围", u"用上了": u"有"},
     u"不认得的栏名", u"C-3 那次的同一个毛病:栏名只要不是数数的工具认的那几个,写了等于没写"),
    (u"C-3 当时那张的原样:把「用上了」写进了「捞到的」里面",
     {u"查了什么": u"搜了权限那几条", u"捞到的": [{u"怎么用": u"照它改了范围"}]},
     u"结构上永远是 0", u"C-3 开卡时真这么错过一次,账只能追加,那一笔改不回去"),
]


def 真卡():
    坏 = []
    for f in sorted(glob.glob(os.path.join(u"cards", u"*.json"))):
        c = json.loads(io.open(f, encoding=u"utf-8").read())
        抱怨 = 查判据(c.get(u"accept") or [])
        print(u"  %s %s" % (u"绿" if not 抱怨 else u"红", f))
        for b in 抱怨:
            print(u"      %s" % b)
            坏.append(f)
    return 坏


def 样卡():
    坏 = []
    for 名, accept, 字眼, 出处 in 坏样:
        抱怨 = u" ".join(查判据(accept))
        中 = 字眼 in 抱怨
        print(u"  %s %s  ←  %s" % (u"拦下" if 中 else u"漏了", 名, 出处))
        if not 中:
            坏.append(名)
    for 名, q, 字眼, 出处 in 坏查库:
        抱怨 = u" ".join(查查库(q))
        中 = 字眼 in 抱怨
        print(u"  %s %s  ←  %s" % (u"拦下" if 中 else u"漏了", 名, 出处))
        if not 中:
            坏.append(名)
    return 坏


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] != u"--self":
        c = json.loads(io.open(argv[0], encoding=u"utf-8").read())
        抱怨 = 查判据(c.get(u"accept") or [])
        for b in 抱怨:
            sys.stderr.write(u"%s\n" % b)
        return 1 if 抱怨 else 0
    print(u"盘上的真卡(一张都不许误伤):")
    a = 真卡()
    print(u"坏样卡(每种毛病都得被对应那一条拦下):")
    b = 样卡()
    print(u"\n误伤 %d 张,漏掉 %d 种" % (len(a), len(b)))
    return 1 if (a or b) else 0


if __name__ == u"__main__":
    sys.exit(main())
