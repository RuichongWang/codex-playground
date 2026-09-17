#!/usr/bin/env bash
# 这次改动大到没法认真读了吗?
# 上限 300 行,是按本仓前八次改动定的 —— 41/47/92/134/194/469/754,
# 300 恰好把最后那两次(建 v0、大改造)拦下来,而那两次确实大到读不动。
# reports/ 是证据文件(判官交的日志原文,动辄上万字),不算改动量。
set -u
CAP=300
BASE="${1:-HEAD^}"
N=$(git diff --numstat "$BASE" HEAD -- . ':(exclude)reports' | awk '{a+=$1;d+=$2} END {print a+d+0}')
F=$(git diff --name-only "$BASE" HEAD -- . ':(exclude)reports' | wc -l)
echo "这次改动 ${N} 行 / ${F} 个文件,上限 ${CAP} 行"
[ "$N" -le "$CAP" ] || { echo "太大了,拆成几次 —— 读不动的改动等于没人读" >&2; exit 1; }
