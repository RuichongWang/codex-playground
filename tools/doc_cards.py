# -*- coding: utf-8 -*-
u"""说明书里那些「一条验收条件长什么样」的 JSON 范例,拿真的校验器过一遍。

**为什么要有这个。** 这个仓已经栽过三次同一个跟头:说明书里手抄的东西会慢慢跟实际
对不上,而且**没有任何东西在看着它**。第三次是设计文档里人答那一档的范例还停在
`"判者":"读者"` 这个老写法上 —— 照它原样抄一张卡去开,工具当场拒。
说明书教的写法开不了卡,这比没有范例更糟。

`tools/readme_cmds.py` 管的是说明书里的**命令**认不认得出,这一份管的是说明书里的
**判据范例**能不能真的开卡。两份合起来,手抄的那两类东西才都有人看着。

范例里允许留占位(`<某某>`),所以这里只校形状,不校内容能不能跑。
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from done.card import Refused, validate  # noqa: E402

文件 = [u"README.md", u"CLAUDE.md",
        os.path.join(u"docs", u"DESIGN.md"),
        os.path.join(u".claude", u"skills", u"pattern-library", u"SKILL.md")]

围栏 = re.compile(u"```json\n(.*?)```", re.S)


def 块里的对象(块):
    u"""一个 json 围栏里可能并排放着几个对象(中间空一行)。逐个试,试不出就跳过。"""
    出 = []
    for 片 in re.split(u"\n\\s*\n", 块):
        片 = 片.strip()
        if not 片:
            continue
        try:
            出.append(json.loads(片))
        except ValueError:
            continue
    return 出


def 是判据(o):
    return isinstance(o, dict) and u"问" in o and u"过" in o and u"判者" in o


def main(argv=None):
    根 = (argv or sys.argv[1:] or [u"."])[0]
    查过, 坏 = 0, []
    for 名 in 文件:
        p = os.path.join(根, 名)
        if not os.path.exists(p):
            continue
        s = io.open(p, encoding=u"utf-8").read()
        for 块 in 围栏.findall(s):
            群 = 块里的对象(块)
            # 一张整卡
            卡 = [o for o in 群 if isinstance(o, dict) and isinstance(o.get(u"accept"), list)]
            # 散落的单条判据
            散 = [o for o in 群 if 是判据(o)]
            for c in 卡:
                查过 += 1
                try:
                    validate(c[u"accept"])
                except Refused as e:
                    坏.append((名, c.get(u"id") or u"(没写 id)", e))
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
    for 名, 谁, e in 坏:
        sys.stderr.write(u"%s 里的范例过不了校验:%s —— %s\n" % (名, 谁, e))
    print(u"说明书里的判据范例 %d 条,过不了校验的 %d 条" % (查过, len(坏)))
    return 1 if 坏 else 0


if __name__ == u"__main__":
    sys.exit(main())
