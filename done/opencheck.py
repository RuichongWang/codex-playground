# -*- coding: utf-8 -*-
u"""开卡那一刻的额外体检:不是「这条判据合不合法」,是「这条判据写坏了没有」。

`card.validate` 管的是硬形状(四栏齐不齐、判者认不认得出、有没有一条命令答)。
这一份管的是**只看判据自己的文字就看得出来的那几种写坏**:

  答域和问法对不上   「找出一个…」的「过」只能是「没找到」;「…吗?」只能是「是」或「否」
  答域不明       两种问法都不是 —— 判的人不知道该答什么
  答没找到就写清什么  人来答的找反例判据,没交代怎么算搜过,「没找到」就是个免费答案
  名字和取材对不上   判者名字点了名要读什么,「凭什么答」里却没给他
  查库栏名不认得    开工前查库那一栏栏名自造,数数的工具看不见
  查库缺「用上了」   同上,于是「查到并真用上」那个数结构上永远是 0

**为什么「前移到开卡」只对这几种成立**(库里 C103 那条:核验前移的前提是判定不需要读
被保护的那套状态):这几种只看判据自己的文字就判得了,不需要知道那件活干成没有。
问句有歧义、范围写错这类要读懂那件活才判得了 —— 前移是假的,所以不做。

**这道门的闸不是「它逮着过东西没有」,是「它有没有逮错过」。** 这句话是被打脸两次换来的:

1. 第一版每条检查后面都手写着「它对应账上第几次改判据」。审阅人拿那 14 次逐条核,
   其中两条一次都没命中过 —— 出处是攀附的。于是加了 `tools/openreplay.py` 重放全部历史
   现数,并拿「命中 0 次的不许留」当闸门,当场删了那两条。
2. 下一个审阅人把那个数拆开看:命中最多那条号称 13 次,11 次打在**没有「问」这一栏的
   老格式**上(那一档另有硬形状检查会拒),另外 2 次是**真逮错了** —— 其中一处在
   `packs/coldread.json` 里活着:一句标准是非问,只因为问号后面跟了个括号补语就被判
   答域不明,而那个括号正是上一次修复专门补的。**它拦的是修复,含糊的版本反而过得去。**
   与此同时被删掉的那两条其实是真毛病:判决那一步的答域是照「过」定的,
   「找出一处循环依赖」配「过」=「是」的意思整个反过来。

结论:「从没逮着过」和「逮错过」不是同一件事。前者只说明这类坏法还没发生过 ——
入口检查本来就是为还没发生的事设的;后者是这道门今天就在挡正确的东西。
所以闸门换成后者:`tools/opencheck.py --self` 要求**对现在盘上的每一张卡、每一个判据包、
说明书里的每一条范例都放行**,一处误伤就红。重放那个数留着,但只当读数打印,不当闸。
"""
import os
import re

from done.ledger import Refused

# 判据只有两种问法:找反例的「找出一个…」,和是非问的「…吗?」。两种都不是就是答域不明。
# **两条都别贴死位置。** 贴死过,两处都逮错了:
#   「在这张卡碰过的文件里,找出一个…」——「找出」不在开头,于是没被认成找反例;
#   「…从零开始的吗?(只问这个 —— 不问 clone 源新不新)」—— 问号后面跟了括号补语,
#   于是没被认成是非问。后一句的括号还是上一次修复专门补的(「干净」有两种读法)。
找反例 = re.compile(u"找出")
是问句 = re.compile(u"[吗?？]\\s*$")
尾注 = re.compile(u"[((][^()（）]*[))]\\s*$")


def _去尾注(问):
    u"""把句末的括号补语剥掉再判问法 —— 补语是给答的人的,不改问法。"""
    while True:
        新 = 尾注.sub(u"", 问).strip()
        if 新 == 问.strip():
            return 新
        问 = 新

# 判者的名字里点了名要读什么,卡上「凭什么答」就得真把那样东西给他。
# 只管名字以「审阅人 / 读者」收尾的 —— 那是这个仓给「来读东西的人」起名的惯例;
# 「照说明书跑的人」是来干活的,不在这条管的范围里。
来读的 = re.compile(u"(审阅人|读者)$")
点名的取材 = (
    (u"改动", (u"改动", u"diff")),
    (u"说明书", (u"说明书", u"README", u"docs", u".md")),
    (u"库", (u"库", u"条目", u"catalog")),
    (u"代码", (u"代码", u"文件", u"done/", u"tools/", u".py")),
)

查库栏 = (u"查了什么", u"捞到的", u"用上了", u"没查到的", u"查了没有")

# 这儿有哪几条检查。`tools/opencheck.py --self` 照这张名册打印每条在历史里的读数,
# 并要求每一条对**现在盘上**的卡 / 判据包 / 说明书范例都没有一处误伤。
检查册 = (u"答域和问法对不上", u"答域不明", u"答没找到就写清什么", u"名字和取材对不上",
          u"查库栏名不认得", u"查库缺「用上了」")


def 查判据带名(accept):
    u"""逐条查形状,产出 (检查名, 一句抱怨)。检查名是给重放那一步数数用的。"""
    for c in accept:
        cid, 问, 过 = c.get(u"id"), c.get(u"问") or u"", c.get(u"过")
        判者 = c.get(u"判者")
        # 老卡里 判者 是个裸字符串。那一档由 card.validate 拒,这儿只管别崩。
        判者 = 判者 if isinstance(判者, dict) else {}
        凭 = c.get(u"凭什么答") or u""
        问净 = _去尾注(问)
        if 找反例.search(问净):
            if 过 != u"没找到":
                yield (u"答域和问法对不上",
                       u"%s 是「找出一个…」的问法,「过」只能是「没找到」,现在写的是「%s」"
                       u" —— 判决那一步的答域是照「过」定的,这么写意思整个反过来" % (cid, 过))
            # 命令答的找反例判据不在此列:一次全量扫描就是最彻底的搜,退出码本身就是交代。
            if 判者.get(u"读者") and u"没找到" not in 凭:
                yield (u"答没找到就写清什么",
                       u"%s 由人来答又是找反例,「凭什么答」里要交代一句"
                       u"「答没找到就写清什么」 —— 不交代的话「没找到」是个免费答案" % cid)
        elif 是问句.search(问净):
            if 过 not in (u"是", u"否"):
                yield (u"答域和问法对不上",
                       u"%s 是「…吗?」的问法,「过」只能是「是」或「否」,现在写的是「%s」"
                       % (cid, 过))
        else:
            yield (u"答域不明",
                   u"%s 的「问」既不是「找出一个…」也不是「…吗?」—— "
                   u"答域不明,判的人不知道该答什么" % cid)
        谁 = 判者.get(u"读者") or u""
        if 来读的.search(谁):
            for 词, 线索 in 点名的取材:
                if 词 in 谁 and not any(x in 凭 for x in 线索):
                    yield (u"名字和取材对不上",
                           u"%s 的判者叫「%s」,名字里点了「%s」,可是「凭什么答」里"
                           u"一样这类东西都没给他(%s)—— 名字和取材对不上,"
                           u"他很可能只能答「答不了」"
                           % (cid, 谁, 词, u" / ".join(线索)))


def 查判据(accept):
    u"""只要那一串抱怨(空 = 没毛病)。"""
    return [话 for _, 话 in 查判据带名(accept)]


def 查查库带名(q):
    u"""开工前查库那一栏:栏名得是数数的工具认得的那几个。"""
    if not q:
        return
    多出来 = [k for k in q if k not in 查库栏]
    if 多出来:
        yield (u"查库栏名不认得",
               u"查库那一栏有数数的工具不认得的栏名:%s —— 它认的是 %s"
               % (u"、".join(多出来), u"、".join(查库栏)))
    if q.get(u"查了什么") and u"用上了" not in q:
        yield (u"查库缺「用上了」",
               u"查库记了「查了什么」却没有「用上了」这一栏 —— "
               u"于是「查到并真用上」那个数结构上永远是 0(账上第 27 条、开体检卡那次"
               u"真这么错过一次,账只能追加,那一笔改不回去)。"
               u"一次都没用上也要写「用上了」:「没有,都不对路」")


def 查查库(q):
    return [话 for _, 话 in 查查库带名(q)]


def 拦(accept, 查库=None):
    坏 = 查判据(accept) + 查查库(查库)
    if 坏:
        raise Refused(u"open-shape", u"这张卡的判据写坏了:\n  - " + u"\n  - ".join(坏))
    return True


def 开卡实况(accept, repo=u".", timeout=120):
    u"""开卡这一刻,把每条命令判据先跑一遍,记下它现在是什么颜色。

    **这一条记,不拦。** 它对的是账上第 10 · 12 · 13 次改判据 —— 那三次的毛病都是
    「这条判据的答案永远是同一个」,而恒绿的判据和不存在的判据在判决那一刻一模一样。
    这种毛病机械拦不住(体检卡就该一开卡全绿),但它能变成一个读数:
    开卡时是什么颜色、判决时是什么颜色,两边都记下来,常数就看得见了。

    **命令跑在一个 detached worktree 里,不在你的工作目录里** —— 跟判那一步同一个规矩。
    第一版没这么做,当场把真账写坏了:`make check` 里有一条故意的用例,内容正是
    「往 .done/ledger.jsonl 里追加一行垃圾」,它本来该在 worktree 里跑,
    结果被这一步在真仓库根目录上跑了三遍。**判据里的命令是别人写的字,不是你的**。
    起不了 worktree(比如还没有任何提交)就整段跳过,只记一句为什么。
    """
    import shutil
    import subprocess
    import tempfile
    cmds = [c for c in accept if (c.get(u"判者") or {}).get(u"cmd")
            if isinstance(c.get(u"判者"), dict)]
    if not cmds:
        return []
    tmp = tempfile.mkdtemp(prefix=u"done-open-")
    wt = os.path.join(tmp, u"t")
    p = subprocess.run(u"git worktree add --detach %s HEAD" % wt, shell=True, cwd=repo,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        return [{u"跑不了": u"起不了 worktree:%s"
                 % p.stdout.decode(u"utf-8", u"replace").strip()[:200]}]
    出 = []
    try:
        for c in cmds:
            cmd = c[u"判者"][u"cmd"]
            try:
                r = subprocess.run(cmd, shell=True, cwd=wt, timeout=timeout,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                码 = r.returncode
            except Exception as e:
                码 = u"跑不起来:%s" % e
            出.append({u"id": c.get(u"id"), u"cmd": cmd, u"exit": 码,
                       u"开卡就绿": 码 == 0})
    finally:
        subprocess.run(u"git worktree remove --force %s" % wt, shell=True, cwd=repo,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        shutil.rmtree(tmp, ignore_errors=True)
    return 出
