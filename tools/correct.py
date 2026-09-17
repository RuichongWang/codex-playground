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

**「模型不是 agent」是靠把工具全关掉做到的**:走 `claude -p --disallowedTools …`,
实测这样调用它会明说「我没有文件读取工具」—— 它看不到仓库、翻不了别处,
只能对着你给它的那三样东西答。也可以不调,把评审记录当文件交进来(`--评审`),
两条路产出的记录一模一样。
"""
import io
import json
import os
import sys

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


关工具 = (u"Bash Read Write Edit Glob Grep WebFetch WebSearch Task TodoWrite "
          u"NotebookEdit BashOutput KillShell")
评审模型 = u"claude-haiku-4-5-20251001"


def 问一条(p):
    u"""一次纯模型调用,只给这一条订正的三样东西。工具全关 —— 它翻不了仓库。"""
    import subprocess
    prompt = (u"你在评审一条「订正」。你看不到任何别的东西,只有下面三样。不要猜背景,只对着它们答。\n\n"
              u"【改前】%s\n\n【改后】%s\n\n【订正者说的理由】%s\n\n"
              u"逐条回答这三问,每条只答「合格」或「不合格」:\n"
              u"1. %s\n2. %s\n3. %s\n\n"
              u"三条全「合格」才算通过。**只输出一个 JSON**,不要别的字:\n"
              u'{"通过": true/false, "三问": {"<原样抄上面第1问>": "合格/不合格", '
              u'"<第2问>": "...", "<第3问>": "..."}, "理由": "一句话"}'
              % (p[u"改前"], p[u"改后"], p[u"为什么"], 三问[0], 三问[1], 三问[2]))
    out = subprocess.run([u"claude", u"-p", prompt, u"--model", 评审模型,
                          u"--disallowedTools"] + 关工具.split(),
                         capture_output=True, timeout=300).stdout.decode(u"utf-8", u"replace")
    i, j = out.find(u"{"), out.rfind(u"}")
    if i < 0:
        raise 拒(u"评审没吐出 JSON:%s" % out[:200])
    return json.loads(out[i:j + 1])


def 评审(提案):
    u"""自己发起那几次纯模型调用,拼成一份评审记录。"""
    逐条 = []
    for i, p in enumerate(提案):
        v = 问一条(p)
        v[u"序号"] = i
        逐条.append(v)
    return {u"评审者": u"纯模型调用 %s(工具全关)" % 评审模型, u"逐条": 逐条}


def main(argv=None):
    a = dict(zip(sys.argv[1::2], sys.argv[2::2]))
    if u"--提案" not in a:
        sys.stderr.write(u"用法:correct.py --提案 <json> [--评审 <json>]\n")
        return 2
    提案 = json.loads(io.open(a[u"--提案"], encoding=u"utf-8").read())
    评 = json.loads(io.open(a[u"--评审"], encoding=u"utf-8").read()) if a.get(u"--评审") else 评审(提案)
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
    except 拒 as e:
        sys.stderr.write(u"拒绝:%s\n" % e)
        sys.exit(1)
