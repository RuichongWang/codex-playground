#!/usr/bin/env bash
# 500 行硬顶的执行器。数的是实现代码;必红用例(redcases.py)不计 ——
# 否则这条硬顶会奖励少写用例,那正是它要防的那个形。
set -u
CAP=500
N=$(cat done/*.py check.py | grep -v '^[[:space:]]*$' | grep -v '^[[:space:]]*#' | wc -l)
echo "实现代码 ${N} 行 / 上限 ${CAP}"
[ "$N" -le "$CAP" ] || { echo "超顶了 —— 要加东西,先砍一条规矩" >&2; exit 1; }
