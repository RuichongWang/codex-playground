# -*- coding: utf-8 -*-
u"""同一句话在仓里存了几份 —— 找出来,每一份都得有人交代一句为什么。

**这道检查是被同一个形状连着咬两次换来的。**

一句「每一条判据 = 一个只能答「是 / 否 / 答不了」的问题」,在仓里存了四份:
说明书、协作约定、设计文档、`done/card.py` 的自述。答案值后来多了一组
(找反例那一档答的是「找到 / 没找到」),一轮只改掉两份,另外两份原封不动 ——
而那次提交说明里还写着「说明书跟着改了」。照没改那份写出来的报告,实跑当场被拒。
**一句话存了几份,改一份不会有任何东西发现另外几份**,而每一份单独读都通顺。

所以这儿不管「对不对」——对不对要读懂那件事,前移是假的。这儿只管一件机械的事:
**跨文件一模一样的长句子,有几处,是不是都认领过。**两个方向都红:

- 冒出一处没认领的 → 你又抄了一份,写一句为什么它得有两份
- 认领过的那一处找不到了 → **两份里你只改了一份**,正是上面那次栽的样子

阈值 40 个字,是量出来的:那句栽过的话在两份之间的公共串是 46 个字,
再高一档(48)就漏掉它。不是拍脑袋定的。

    python3 tools/saidtwice.py
"""
import ast
import collections
import glob
import io
import os
import re
import sys

字数 = 40

看的 = (u"README.md", u"CLAUDE.md", os.path.join(u"docs", u"DESIGN.md"))

# 认下的重复:每一条都得有一句为什么它值得存两份。
# **这不是豁免名单,它往严的方向漂** —— 名单里的句子只要有一份被改动,
# 这条就再也匹配不上,当场红(「你只改了一份」)。
认下的 = (
    (u' **给一件干完的活发一个「它自己伪造不了的 `done`」,依据是开卡时就冻住的 accept criteria, 并把这件事记成一行改不掉的账。** ',
     u"这个项目的一句话定义,说明书和设计文档的开头各要一句 —— 少一句,那份就没有入口"),
    (u' = 一个只能从三个值里挑一个来答的问题,带着「凭什么答」和「哪边算过」。 唯一的区别是谁来答:一条命令,还是一个读者。** ',
     u"判据形态的总述,两份文档各要一句。**这一处正是栽过的那一处** —— 两边的答案值现在都不手抄了,各自指向 `python3 tools/answerdomain.py`"),
    (u' ```json {"id":"…","题面":"…","引":["<包名>@<版本>"],"accept":[ …本卡自己的… ]} ``` **这里不',
     u"判据包怎么引的示意块,两份文档各要一个"),
    (u'。 ```json {"id":"a1","问":"make check 退出码是 0 吗?","过":"是", "判者":{"cmd":"make check","答是":"exit0"},"凭什么答":"命令的退出码与输出"} {"id":"',
     u"最短的一张范例卡,两份文档各要一个;而且必须是能真开卡的那一份 —— `tools/doc_cards.py` 会把两边都拿去开一次"),
    (u'上一条由判官答的 「有没有哪个文件在同时干好几件不相干的事」。`tools/loc.sh` 只报数,不拦人。 ',
     u"三条上限里的第一条:协作约定和设计文档各要一份,前者是给人读的规矩,后者是给人查的设计"),
    (u'必红用例返回 True = 「它确实红了」;绿对照返回 True = 「正常那条路走通了」。 ',
     u"红绿两个返回值的约定,规矩表和用例表各要一句 —— 少一句,写用例的人会把真假写反"),
    (u'条 `{答, 引文, 证据}`,而 **`引文` 必须是 `证据` 的逐字子串**',
     u"人来答的那条路最硬的一条规矩,两份文档各要一句"),
)


def _散文(f):
    u"""markdown 全文;python 只取自述和注释 —— 代码本身重复是另一回事,不归这儿管。"""
    src = io.open(f, encoding=u"utf-8").read()
    if not f.endswith(u".py"):
        return src
    out = []
    try:
        t = ast.parse(src)
    except SyntaxError:
        return u""
    for node in ast.walk(t):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)):
            d = ast.get_docstring(node)
            if d:
                out.append(d)
    out += [l.strip().lstrip(u"#").strip()
            for l in src.splitlines() if l.strip().startswith(u"#")]
    return u"\n".join(out)


def 源():
    名单 = list(看的) + sorted(glob.glob(os.path.join(u"done", u"*.py"))
                              + glob.glob(os.path.join(u"tools", u"*.py"))
                              + [u"check.py", u"redcases.py"])
    return [(f, re.sub(u"\\s+", u" ", _散文(f))) for f in 名单 if os.path.exists(f)]


def 找重复(文本, n=字数):
    u"""跨文件一模一样、长度 >= n 的极大串;返回 {串: (文件, …)}。"""
    格 = collections.defaultdict(set)
    for f, t in 文本:
        for i in range(len(t) - n + 1):
            格[t[i:i + n]].add(f)
    共有 = set(g for g, v in 格.items() if len(v) > 1)
    出 = {}
    for f, t in 文本:
        i = 0
        while i <= len(t) - n:
            if t[i:i + n] in 共有:
                j = i
                while j <= len(t) - n and t[j:j + n] in 共有:
                    j += 1
                出[t[i:j + n - 1]] = tuple(sorted(格[t[i:i + n]]))
                i = j
            else:
                i += 1
    return 出


def 查(文本, 名单=认下的):
    u"""返回 (没认领的, 认领了却找不到的)。两样都空才算过。"""
    找到 = 找重复(文本)
    认 = [x[0] for x in 名单]
    没认领 = [(s, 找到[s]) for s in sorted(找到) if s not in 认]
    丢了 = [s for s in 认 if s not in 找到]
    return 没认领, 丢了


def main():
    没认领, 丢了 = 查(源())
    for s, fs in 没认领:
        sys.stderr.write(u"这句话在 %s 里各有一份,没人认领过:\n  %s\n"
                         % (u"、".join(fs), s[:90]))
    for s in 丢了:
        sys.stderr.write(u"认下的这一处现在对不上了 —— 两份里八成只改了一份:\n  %s\n"
                         % s[:90])
    print(u"跨文件重复的长句 %d 处,认下的 %d 处,没认领的 %d 处,认了却找不到的 %d 处"
          % (len(认下的) - len(丢了) + len(没认领), len(认下的), len(没认领), len(丢了)))
    return 1 if (没认领 or 丢了) else 0


if __name__ == u"__main__":
    sys.exit(main())
