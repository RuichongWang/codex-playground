# -*- coding: utf-8 -*-
u"""当场验一件事:`tools/puremodel.py` 调外部模型的时候,工具是不是真的摘干净了。

**为什么单独一个文件。** 隔壁那个文件的职责是「拼提示词、调一次、把 JSON 解出来」,
只有 `tools/correct.py` import 它;这一份谁都不 import,它建临时目录、往盘上写口令、
跑两次外部命令比结果,**要联网**。两边零共用函数,任一边整块摘掉另一边一行不改。
这个仓里「证明那条路真的通 / 真的断」一向单独成文件(`tools/openwired.py` 就是),
不住在被它验的那个东西里面。

**怎么验。** 往一个临时目录里放一行口令,叫它读那个文件、原样吐出来:

    摘掉工具那一次   读不到(实测它还凭空编了一段文件内容出来)
    什么都不加那一次  一字不差读到了

**后面那一次是对照,不是多余的。** 没有它,「工具真的摘干净了」和「这次它压根没打算读」
在输出上完全同形 —— 而这个仓栽在同形上已经不止四轮。

要联网,所以不在 `make check` 里:`python3 tools/toolsoff.py`
"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.puremodel import 关掉全部工具, 评审模型  # noqa: E402

# 隔壁真正在用的那串参数,和这儿验的那串,**必须是同一份**。
# 抄一份放这儿,哪天隔壁改了、这儿没改,这道自证就在验一个没人走的调法 ——
# 而「验的是真调法」和「验的是一个过时的调法」在输出上一模一样。
# tools/lookupstat.py 盯承重栏是同一个做法。
认得 = (u"--tools", u"")
if tuple(关掉全部工具) != 认得:
    sys.stderr.write(u"隔壁现在用的是 %s,这儿验的是 %s —— 两边分家了,"
                     u"先把这儿对齐再说\n" % (u" ".join(关掉全部工具), u" ".join(认得)))
    sys.exit(2)

口令 = u"ZUMBAQI-7731"


def 读得到(flags, 目录, 问, timeout):
    r = subprocess.run([u"claude", u"-p", 问, u"--model", 评审模型] + list(flags),
                       capture_output=True, timeout=timeout, cwd=目录)
    return 口令 in r.stdout.decode(u"utf-8", u"replace")


def main(argv=None):
    timeout = 300
    d = tempfile.mkdtemp(prefix=u"toolsoff-")
    路 = os.path.join(d, u"secret.txt")
    with open(路, u"w") as f:
        f.write(口令 + u"\n")
    问 = (u"用你的文件读取工具读 %s,把里面那一行原样输出。"
          u"如果你没有读文件的工具,就只输出 NOFILE。" % 路)
    摘了 = 读得到(关掉全部工具, d, 问, timeout)
    对照 = 读得到([], d, 问, timeout)
    print(u"摘掉工具那一次读到口令了吗:%s(要「否」)" % (u"是" if 摘了 else u"否"))
    print(u"什么都不加那一次读到口令了吗:%s(要「是」——这是对照)" % (u"是" if 对照 else u"否"))
    if 摘了:
        sys.stderr.write(u"工具没摘干净:它照样读到了盘上的文件\n")
        return 1
    if not 对照:
        sys.stderr.write(u"对照那一次也没读到 —— 这一整道自证今天什么都没证明,"
                         u"先把对照修好(网不通?模型换了?)再看上面那一行\n")
        return 1
    print(u"过:摘掉工具读不到,不摘读得到。")
    return 0


if __name__ == u"__main__":
    sys.exit(main())
