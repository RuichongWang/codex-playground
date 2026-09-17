#!/usr/bin/env bash
# 这次手册长了多少?
#
# 卡的是**手册那一侧**,不是代码。代码有 500 行总量上限管着(tools/loc.sh),
# 手册此前一条限制都没有 —— 而上一个项目烂掉的正是手册那一侧:
# 条文可以先写下来、执行器以后再说,边际成本接近零,于是涨到认知上限。
#
# 300 是按本仓历史定的:每次手册改动 0/0/13/23/51/64/157/194,从没超过 194。
# 它是个天花板,不是勒脖子 —— 真撞上说明这一次在往手册里灌东西,该停下来看一眼。
set -euo pipefail   # 出任何错就当场失败 —— 一个报了错还判过的检查,比没有检查更坏
CAP=300
BASE="${1:-HEAD^}"
DOCS="README.md CLAUDE.md docs"
N=$(git diff --numstat "$BASE" HEAD -- $DOCS | awk '{a+=$1;d+=$2} END {print a+d+0}')
F=$(git diff --name-only "$BASE" HEAD -- $DOCS | wc -l)
echo "这次手册改动 ${N} 行 / ${F} 个文件,上限 ${CAP} 行"
[ "$N" -le "$CAP" ] || { echo "手册一次长太多了 —— 拆开,或者先问问这些字是不是真要写" >&2; exit 1; }
