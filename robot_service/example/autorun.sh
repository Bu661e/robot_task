#!/bin/bash
# autorun.sh - 自动运行机械臂抓取放置任务脚本
# 该脚本用于运行 task_armPickPlace 任务

set -e

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# 获取 Isaac Sim 根目录（假设脚本在 seki_demos/task_armPickPlace/ 下）
ISAAC_SIM_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

# 切换到任务目录
cd "$SCRIPT_DIR"

# 使用 Isaac Sim 的 python.sh 来运行主程序
# python.sh 会自动设置所需的环境变量和 Python 路径
"$ISAAC_SIM_ROOT/python.sh" "$SCRIPT_DIR/main_task_armpickplace.py" "$@"
