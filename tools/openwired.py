# -*- coding: utf-8 -*-
u"""拿一张写坏的卡,走**真的开卡命令**跑一遍,看它到底会不会被拒。

跟 `tools/opencheck.py --self` 问的不是一回事:那一份只证明检查器自己拦得住,
这一份证明**开卡那条路真的经过它** —— 一个没被接上的检查器和一个不存在的检查器,
在开卡那一刻是一样的。

所以这里不 import 那几个检查函数,而是起一本空账、写一张坏卡、敲 `done.cli open`,
看退出码和它印出来的那句话。顺带跑一张好卡,确认这道门没把正常的挡在外面。
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

好命令 = {u"id": u"g1", u"问": u"跑得通吗?", u"过": u"是",
         u"判者": {u"cmd": u"true", u"答是": u"exit0"}, u"凭什么答": u"退出码"}

坏卡 = {u"id": u"wired-bad", u"题面": u"一张故意写坏的卡:问句既不是找反例也不是是非问,答域不明",
       u"accept": [好命令,
                  {u"id": u"x1", u"问": u"这次改得怎么样", u"过": u"是",
                   u"判者": {u"cmd": u"true", u"答是": u"exit0"}, u"凭什么答": u"输出"}]}
好卡 = {u"id": u"wired-ok", u"题面": u"一张正常的卡", u"accept": [好命令]}


def 开(d, 卡):
    f = os.path.join(d, 卡[u"id"] + u".json")
    io.open(f, u"w", encoding=u"utf-8").write(json.dumps(卡, ensure_ascii=False))
    账 = os.path.join(d, u"ledger.jsonl")
    头 = subprocess.run([sys.executable, u"-m", u"done.cli", u"--ledger", 账, u"head"],
                       cwd=根, stdout=subprocess.PIPE).stdout.decode(u"utf-8").strip()
    p = subprocess.run([sys.executable, u"-m", u"done.cli", u"--ledger", 账, u"open", f,
                        u"--chain-head", 头, u"--by", u"wired"],
                       cwd=根, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout.decode(u"utf-8").strip()


def main():
    d = tempfile.mkdtemp(prefix=u"wired-")
    try:
        码, 话 = 开(d, 坏卡)
        print(u"写坏的卡 → 退出码 %s\n  %s" % (码, 话.replace(u"\n", u"\n  ")))
        # 认的是那条检查自己的话,不是「退出码非 0」—— 换个理由报错也算绕过了它。
        拦住了 = 码 != 0 and u"答域不明" in 话
        码2, 话2 = 开(d, 好卡)
        print(u"正常的卡 → 退出码 %s\n  %s" % (码2, 话2.replace(u"\n", u"\n  ")))
        放行了 = 码2 == 0
        if 拦住了 and 放行了:
            print(u"\n开卡这条路确实经过那道检查:坏卡被拒、好卡照开")
            return 0
        if not 拦住了:
            sys.stderr.write(u"开卡把一张写坏的卡放进来了 —— 检查器没被接上,"
                             u"或者接上了但这条路绕过了它\n")
        if not 放行了:
            sys.stderr.write(u"开卡把一张正常的卡也挡了 —— 这道门误伤\n")
        return 1
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == u"__main__":
    sys.exit(main())
