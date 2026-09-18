# -*- coding: utf-8 -*-
u"""说明书里那些「一条验收条件长什么样」的 JSON 范例,拿真的校验器过一遍。

**为什么要有这个。** 这个仓已经栽过三次同一个跟头:说明书里手抄的东西会慢慢跟实际
对不上,而且**没有任何东西在看着它**。第三次是设计文档里人答那一档的范例还停在
`"判者":"读者"` 这个老写法上 —— 照它原样抄一张卡去开,工具当场拒。
说明书教的写法开不了卡,这比没有范例更糟。

`tools/readme_cmds.py` 管的是说明书里的**命令**认不认得出,这一份管的是说明书里的
**判据范例**能不能真的开卡。两份合起来,手抄的那两类东西才都有人看着。

**开卡那道体检(`done/opencheck.py`)也要在这儿走一遍。** 第一版漏了这一步,
结果就是:新加的一条开卡检查当场把说明书自己的范例判成不合格,而这个工具还是绿的 ——
它只跑老的形状校验。一个没被接上的检查器和一个不存在的检查器,在那一刻是一样的。

**报告那一份范例也在这儿。** 说明书里除了「一条判据长什么样」,还印着一份
「判官报告长什么样」,而那份是照着上面那条判据写的。真栽过:那条判据的「过」
从是非问改成了找反例,底下报告范例的「答」没跟着改 —— 照它原样交一份上去,
判决那一步当场拒。报告范例解不开就没法核它答得对不对,所以两样必须在一个地方看:
**拿掉判据那一半,报告这一半连「这条的「过」是什么」都问不出来。**

范例里允许留占位(`<某某>`),所以这里只校形状,不校内容能不能跑。
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from done.card import Refused, validate  # noqa: E402
from done.judge import 答域  # noqa: E402
from done.opencheck import 查判据  # noqa: E402

文件 = [u"README.md", u"CLAUDE.md",
        os.path.join(u"docs", u"DESIGN.md"),
        os.path.join(u".claude", u"skills", u"pattern-library", u"SKILL.md")]

围栏 = re.compile(u"```json\n(.*?)```", re.S)


def 块里的对象(块):
    u"""一个 json 围栏里可能并排放着几个对象(中间空一行)。

    解不开的照样要报出来 —— **「核过了」和「跳过了」在一行「0 条不过」上是同形的**。
    真栽过一次:设计文档里有个带省略号的范例,里面手抄的版本号早就过期,
    照它开卡会被拒;这个工具解不开那一块,于是打印出来的还是「0 条不过」。
    所以返回两样:解开的对象,和解不开的片段的头一行。
    """
    出, 解不开 = [], []
    for 片 in re.split(u"\n\\s*\n", 块):
        片 = 片.strip()
        if not 片:
            continue
        try:
            出.append(json.loads(片))
        except ValueError:
            解不开.append(片.split(u"\n")[0][:70])
    return 出, 解不开


def 是判据(o):
    return isinstance(o, dict) and u"问" in o and u"过" in o and u"判者" in o


def 是报告(o):
    return isinstance(o, dict) and isinstance(o.get(u"answers"), dict)


def 查报告(报告们, 判据表):
    u"""照说明书上那份报告范例写一份交上去,判决那一步收不收。

    只校两件形状上的事,不校内容(范例里的引文和证据都是占位):
    答得在这条判据的答域里 · 答「没找到」得带着「搜了什么」那一格。
    点名了一条这几份文档里根本没有的判据,不判红,只说一声没核过。
    """
    坏, 没核 = [], []
    for 名, r in 报告们:
        for cid, a in sorted(r[u"answers"].items()):
            c = 判据表.get(cid)
            if c is None:
                没核.append((名, cid))
                continue
            域 = 答域(c[u"过"])
            if not isinstance(a, dict) or a.get(u"答") not in 域:
                坏.append((名, cid, u"报告范例给的答是「%s」,而这条判据的「过」写的是「%s」,"
                                    u"答只能是 %s"
                           % ((a or {}).get(u"答") if isinstance(a, dict) else a,
                              c[u"过"], u"/".join(域))))
            elif a.get(u"答") == u"没找到" and not a.get(u"搜了什么"):
                坏.append((名, cid, u"报告范例答「没找到」却没有「搜了什么」这一格"))
    return 坏, 没核


def main(argv=None):
    根 = (argv or sys.argv[1:] or [u"."])[0]
    查过, 坏, 解不开 = 0, [], []
    判据表, 报告们 = {}, []
    for 名 in 文件:
        p = os.path.join(根, 名)
        if not os.path.exists(p):
            continue
        s = io.open(p, encoding=u"utf-8").read()
        for 块 in 围栏.findall(s):
            群, 剩 = 块里的对象(块)
            解不开.extend((名, x) for x in 剩)
            # 一张整卡
            卡 = [o for o in 群 if isinstance(o, dict) and isinstance(o.get(u"accept"), list)]
            # 散落的单条判据
            散 = [o for o in 群 if 是判据(o)]
            报告们 += [(名, o) for o in 群 if 是报告(o)]
            for o in 散 + [x for c in 卡 for x in c[u"accept"] if 是判据(x)]:
                if o.get(u"id"):
                    判据表.setdefault(o[u"id"], o)
            for c in 卡:
                查过 += 1
                try:
                    validate(c[u"accept"])
                except Refused as e:
                    坏.append((名, c.get(u"id") or u"(没写 id)", e))
                坏.extend((名, c.get(u"id") or u"(没写 id)", x)
                          for x in 查判据(c[u"accept"]))
            if 散:
                查过 += len(散)
                # 「一张卡至少要有一条命令来答」是对**整张卡**的要求,不是对单条范例的。
                # 说明书里的范例是拆开写的,一个围栏里可能只有人答那一档 ——
                # 那不是范例的毛病。所以缺命令的时候补一条假的进去,只校每条自己的形状。
                组 = list(散)
                if not any(isinstance(o.get(u"判者"), dict) and o[u"判者"].get(u"cmd")
                           for o in 组):
                    组.append({u"id": u"__凑数__", u"问": u"?", u"过": u"是",
                              u"判者": {u"cmd": u"true", u"答是": u"exit0"},
                              u"凭什么答": u"-"})
                try:
                    validate(组)
                except Refused as e:
                    坏.append((名, u"/".join(str(o.get(u"id")) for o in 散), e))
                坏.extend((名, 谁, x) for 谁, x in
                          ((o.get(u"id"), x) for o in 散 for x in 查判据([o])))
    报告坏, 报告没核 = 查报告(报告们, 判据表)
    坏 += 报告坏
    查过 += len(报告们)
    for 名, 谁, e in 坏:
        sys.stderr.write(u"%s 里的范例过不了校验:%s —— %s\n" % (名, 谁, e))
    print(u"说明书里的范例(判据 + 照它写的报告)%d 条,过不了校验的 %d 条"
          % (查过, len(坏)))
    for 名, cid in 报告没核:
        print(u"  %s 里那份报告范例点名的 %s,这几份文档里没有对应的判据,没核"
              % (名, cid))
    if 解不开:
        # 不判红:说明书里本来就有带省略号、带占位的示意块,那不是毛病。
        # 但**这几块这个工具没看过**,得说出来,别让「0 条不过」读成「全都核过了」。
        print(u"另有 %d 块 json 这个工具解不开、没核(带省略号或占位的示意块):" % len(解不开))
        for 名, 头 in 解不开:
            print(u"  %s: %s" % (名, 头))
    return 1 if 坏 else 0


if __name__ == u"__main__":
    sys.exit(main())
