# -*- coding: utf-8 -*-
u"""把开卡体检的每一条检查,拿仓库的**全部历史**重放一遍,数它各逮着过几次。

**为什么要有这个。** 第一版那几条检查,每条后面都手写着「它对应账上第几次改判据」。
一个审阅人拿账上那 14 次逐条比,发现其中两条在整个历史里一次都没命中过 ——
手写的出处是攀附的,而配着的坏样卡是为了让它变红现编的。
**一张现编的坏样卡,和一条从没逮着过东西的检查,在「它值不值得存在」这一问上是同形的。**

所以这一份把那句话变成一个数:
- 卡(`cards/**.json`)、判据包(`packs/*.json`)、说明书里的 json 范例 —— 每个提交里的
  每一版都取出来,去重之后逐条跑检查;
- 账上每一条开卡记录的「查库」那一栏,跑查库那两条检查。

**这个数当过一阵闸门(命中 0 次的不许留),那是错的,现在只印不拦** ——
按那条闸门当场删掉的两条是真检查:「从没逮着过」只说明这类坏法还没发生过,
而入口检查本来就是为还没发生的事设的。闸门在 `tools/opencheck.py` 的「有没有逮错过」那一边。

用法:
    python3 tools/openreplay.py        打一张表:每条检查命中几次、头一次命中在哪
"""
import io
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from done.opencheck import 检查册, 查查库带名, 查判据带名  # noqa: E402

判据路径 = re.compile(u"^(cards/.*\\.json|packs/.*\\.json)$")
说明书 = (u"README.md", u"CLAUDE.md", u"docs/DESIGN.md",
          u".claude/skills/pattern-library/SKILL.md")
围栏 = re.compile(u"```json\n(.*?)```", re.S)


def _跑(args):
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return p.stdout.decode(u"utf-8", u"replace") if p.returncode == 0 else u""


def 历史里的判据组():
    u"""产出 (出处, 一组判据)。同样内容只出一次。"""
    见过 = set()
    for 提交 in _跑([u"git", u"rev-list", u"HEAD"]).split():
        树 = _跑([u"git", u"ls-tree", u"-r", u"--name-only", 提交]).split(u"\n")
        for 路 in 树:
            if not (判据路径.match(路) or 路 in 说明书):
                continue
            文 = _跑([u"git", u"show", u"%s:%s" % (提交, 路)])
            if not 文:
                continue
            for 组 in 抠判据(路, 文):
                键 = json.dumps(组, sort_keys=True, ensure_ascii=False)
                if 键 in 见过:
                    continue
                见过.add(键)
                # 没有「问」这一栏的是这套栏目存在之前的老格式,由 card.validate 拒 ——
                # 不是这道门的事。数进来只会让某条检查的读数虚高(真发生过:虚高到 13)。
                组 = [c for c in 组 if isinstance(c, dict) and c.get(u"问")]
                if 组:
                    yield (u"%s %s" % (提交[:7], 路), 组)


def 抠判据(路, 文):
    u"""一份文件里可能有卡(accept)、判据包(判据)、或说明书里散落的范例。"""
    if 路.endswith(u".json"):
        try:
            o = json.loads(文)
        except ValueError:
            return
        for k in (u"accept", u"判据"):
            if isinstance(o.get(k), list):
                yield o[k]
        return
    for 块 in 围栏.findall(文):
        for 片 in re.split(u"\n\\s*\n", 块):
            片 = 片.strip()
            if not 片:
                continue
            try:
                o = json.loads(片)
            except ValueError:
                continue    # 带省略号的示意块,这儿只数命中,跳过不影响结论
            if isinstance(o, dict) and isinstance(o.get(u"accept"), list):
                yield o[u"accept"]
            elif isinstance(o, dict) and u"问" in o and u"过" in o:
                yield [o]


def 账上的查库(账=os.path.join(u".done", u"ledger.jsonl")):
    if not os.path.exists(账):
        return
    for 行 in io.open(账, encoding=u"utf-8"):
        try:
            r = json.loads(行)
        except ValueError:
            continue
        b = r.get(u"body") or {}
        if b.get(u"查库"):
            # seq 在记录顶层,不在 body 里 —— 取错了就打印成「账第 ? 条」。
            yield (u"账第 %s 条 %s" % (r.get(u"seq", u"?"), b.get(u"card")), b[u"查库"])


def 数():
    u"""返回 {检查名: (命中次数, [头几个出处])}。次数是全部,出处只留前三个。"""
    命中 = {}
    def 记(名, 出处):
        次, 例 = 命中.setdefault(名, [0, []])
        命中[名][0] = 次 + 1
        if len(例) < 3:
            例.append(出处)
    for 出处, 组 in 历史里的判据组():
        for 名, _ in 查判据带名(组):
            记(名, 出处)
    for 出处, q in 账上的查库():
        for 名, _ in 查查库带名(q):
            记(名, 出处)
    return 命中


def main(argv=None):
    u"""名册上**每一条**都印一行,包括 0 次的那几条。

    上一版只印命中过的那几条:于是一条命中 0 次的检查,和一条根本不在名册上的检查,
    在这张表上逐字同形 —— 而这个数存在的全部理由就是让「它逮着过没有」看得见。
    名册六条却只印出四行,说明书还写着「每条检查在历史里逮着过几次」。
    """
    命中 = 数()
    for 名 in 检查册:
        次, 例 = 命中.get(名, (0, []))
        print(u"%-18s 命中 %d 次%s"
              % (名, 次, (u",例如 " + u" · ".join(例)) if 例 else u"(这类坏法还没发生过)"))
    野 = [名 for 名 in 命中 if 名 not in 检查册]
    if 野:
        print(u"\n名册(done/opencheck.py 的 检查册)上没有,历史里却命中过:%s"
              % u" · ".join(sorted(野)))
        return 1
    return 0


if __name__ == u"__main__":
    sys.exit(main())
