# -*- coding: utf-8 -*-
u"""纯模型问一条 —— 调外面那个命令行,**把工具全摘掉**,只让它对着给它的几行字答。

**为什么单独一个文件。** `tools/correct.py` 管的是那条规矩:订正得过一次评审才准写进库。
那条规矩不关心评审是怎么问出来的 —— 评审记录也可以直接当文件交进去(`--评审`),
两条路产出的记录一模一样。**把这一段整个拿掉,那条规矩一行都不用动**,
所以它本来就不该跟规矩挤在一个文件里。

**「是模型不是 agent」现在靠 `--tools ""`,不再靠手抄一张要关掉的工具名单。**
上一版手抄了十三个工具名走 `--disallowedTools`。那是一张**黑名单**:对方哪天加一个新工具,
这张单子就静默地漏一个 —— 而「名单齐全」和「名单漏了一个」在这边看起来一模一样,
没有任何东西会发现。`--tools ""` 是一张**空白的准入名单**:新加的工具进不来。
它只会往紧了漂,不会往松了漂,于是没有东西需要看着它。

**这句话是实测出来的,不是读文档读出来的**(`python3 tools/puremodel.py --自证`):
往盘上放一行口令,叫它读那个文件、原样吐出来 ——

    --tools ""    读不到(实测它还凭空编了一段文件内容出来)
    什么都不加     一字不差读到了

**后面那一次是对照,不是多余的。** 没有它,「工具真的摘干净了」和「这次它压根没打算读」
在输出上完全同形。要联网,所以这一道不在 `make check` 里,是手动跑的。
"""
import json
import os
import subprocess
import sys
import tempfile

评审模型 = u"claude-haiku-4-5-20251001"
# 空的准入名单 = 一个工具都不给。**别换回黑名单**,理由见上面。
关掉全部工具 = (u"--tools", u"")


class 问不出来(Exception):
    pass


def _调(prompt, cwd=None, timeout=300):
    r = subprocess.run([u"claude", u"-p", prompt, u"--model", 评审模型]
                       + list(关掉全部工具),
                       capture_output=True, timeout=timeout, cwd=cwd)
    return r.stdout.decode(u"utf-8", u"replace")


def 问一条(p, 三问):
    u"""一次纯模型调用,只给这一条订正的三样东西:改前、改后、为什么。"""
    prompt = (u"你在评审一条「订正」。你看不到任何别的东西,只有下面三样。不要猜背景,只对着它们答。\n\n"
              u"【改前】%s\n\n【改后】%s\n\n【订正者说的理由】%s\n\n"
              u"逐条回答这三问,每条只答「合格」或「不合格」:\n"
              u"1. %s\n2. %s\n3. %s\n\n"
              u"三条全「合格」才算通过。**只输出一个 JSON**,不要别的字:\n"
              u'{"通过": true/false, "三问": {"<原样抄上面第1问>": "合格/不合格", '
              u'"<第2问>": "...", "<第3问>": "..."}, "理由": "一句话"}'
              % (p[u"改前"], p[u"改后"], p[u"为什么"], 三问[0], 三问[1], 三问[2]))
    out = _调(prompt)
    i, j = out.find(u"{"), out.rfind(u"}")
    if i < 0:
        raise 问不出来(u"评审没吐出 JSON:%s" % out[:200])
    return json.loads(out[i:j + 1])


def 评审(提案, 三问):
    u"""自己发起那几次纯模型调用,拼成一份评审记录。"""
    逐条 = []
    for i, p in enumerate(提案):
        v = 问一条(p, 三问)
        v[u"序号"] = i
        逐条.append(v)
    return {u"评审者": u"纯模型调用 %s(工具全摘掉)" % 评审模型, u"逐条": 逐条}


def 自证(timeout=300):
    u"""当场验一次「工具真的摘干净了」。**一定要跑对照那一次** —— 见文件开头。"""
    d = tempfile.mkdtemp()
    口令 = u"ZUMBAQI-7731"
    with open(os.path.join(d, u"secret.txt"), u"w") as f:
        f.write(口令 + u"\n")
    q = (u"用你的文件读取工具读 %s,把里面那一行原样输出。"
         u"如果你没有读文件的工具,就只输出 NOFILE。" % os.path.join(d, u"secret.txt"))
    def 读得到(flags):
        r = subprocess.run([u"claude", u"-p", q, u"--model", 评审模型] + flags,
                           capture_output=True, timeout=timeout, cwd=d)
        return 口令 in r.stdout.decode(u"utf-8", u"replace")
    摘了 = 读得到(list(关掉全部工具))
    对照 = 读得到([])
    print(u"摘掉工具那一次读到口令了吗:%s(要「否」)" % (u"是" if 摘了 else u"否"))
    print(u"什么都不加那一次读到口令了吗:%s(要「是」——这是对照)" % (u"是" if 对照 else u"否"))
    if 摘了:
        sys.stderr.write(u"工具没摘干净:它照样读到了盘上的文件\n")
        return 1
    if not 对照:
        sys.stderr.write(u"对照那一次也没读到 —— 这一整道自证今天什么都没证明,"
                         u"先把对照修好(换个模型?网不通?)再看上面那一行\n")
        return 1
    print(u"过:摘掉工具读不到,不摘读得到。")
    return 0


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] == u"--自证":
        return 自证()
    sys.stderr.write(u"这个文件是给 tools/correct.py 用的。"
                     u"想当场验一次工具摘没摘干净:python3 tools/puremodel.py --自证(要联网)\n")
    return 2


if __name__ == u"__main__":
    sys.exit(main())
