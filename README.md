# codex-playground

## `done` —— 一个发 `done` 的最小硬核

**给一件干完的活发一个「它自己伪造不了的 `done`」,依据是开卡时就冻住的 accept criteria,
并把这件事记成一行改不掉的账。**

设计:[`docs/DESIGN.md`](docs/DESIGN.md)(10 分钟读完)· 零依赖,Python 3 标准库

---

## 五分钟跑通第一张卡

```bash
make check                                   # 七条规矩各跑一次必红用例 + 绿对照
python3 -m done.cli head                     # 看账的头(第一次是 64 个 0)

# 开卡:accept criteria 落账即冻结
python3 -m done.cli open cards/C-1.json --chain-head <上面那个头> --by alex

# 干活…… 然后判。判的是一个 commit,在临时 worktree 里跑,不是判工作区
# --eye 的值带空格,必须整个用引号包起来;--at 收的是任何 commit-ish(HEAD / sha / tag)
python3 -m done.cli judge cards/C-1.json --chain-head <新的头> --at HEAD \
        --eye "a3=pass:你的名字:照 README 跑通了"

python3 -m done.cli log                      # 看账
python3 -m done.cli verify                   # 查账有没有被改过
```

`--chain-head` 每次都要传:**写入之前你必须先看过账的头。**
它挡的是**静默**篡改,不是有决心的对手 —— 这一点写在设计的 `U2` 里,没有夸大。

---

## 卡长什么样

`cards/C-1.json` 就是真的那张,下面是它逐字的样子(三条,别的卡照这个写):

```json
{"id": "C-1", "题面": "把 done v0 建出来", "accept": [
  {"id":"a1","判据":"make check 全绿","档":"auto","怎么验":{"cmd":"make check","期望":"exit0"}},
  {"id":"a2","判据":"实现代码不超过 500 行","档":"auto","怎么验":{"cmd":"./tools/loc.sh","期望":"exit0"}},
  {"id":"a3","判据":"没读过设计的人 5 分钟跑通","档":"eye",
   "靠什么兜":{"谁":"冷读者(没读过设计的人)","看什么":"从零 clone 一份,只照 README 跑一遍"}}
]}
```

- **`auto`** —— 一条命令 + 一个期望,判的时候真跑
- **`eye`** —— 必须写「谁」和「看什么」。写成「人工复核」当场拒:不指向一个具体的人,等于没写
- **一张卡至少一条 `auto`。全是 `eye` 的卡开不了** —— 否则 `done` 退化成自评

判决**逐条出,不合成总分**。一条不过,整卡不过。verdict 里出现 `score` / `总分` / `percent` 一律拒收。

改判据?**允许,但要留疤**:走 `amend`,写清为什么,**这张卡此前的 verdict 当场全部作废**。

---

## 七条规矩

`make check` 的输出就是这张表。每条同时有**执行器 · 必红用例 · 绿对照**,三样缺一这条规矩不存在。
上限七条 —— **要加一条,先砍一条**。

| | 规矩 | 执行器 |
|---|---|---|
| R1 | 账只能追加 | `ledger.verify` |
| R2 | 开卡必须带 accept,且至少一条 auto | `card.validate` |
| R3 | accept 预注册即冻结 | `judge.judge` |
| R4 | 判的那只手写不到账 | `ledger.ReadOnly.append` |
| R5 | verdict 逐条、每条带 evidence、不合成总分 | `judge.validate_verdict` |
| R6 | 改 accept 必须留疤 | `card.amend` |
| R7 | 每条规矩必须有一条会红的用例 | `check.main` |

**R7 是自指的那条**:把任一执行器换成恒真,它的必红用例就该不红了 —— 不红则 `make check` 判红。

---

### 别的分支

`claude/pattern-hierarchy-experiment` —— 跨行业 pattern 库实验(与本主题独立)。
