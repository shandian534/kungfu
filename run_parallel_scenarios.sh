#!/bin/bash
# 运行并行测试场景 (12-19)

KF_HOME=${KF_HOME:-/Users/shandian/kungfu}
PYTHON=${PYTHON:-/usr/local/bin/python3.9}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================================"
echo "并行性能测试 - 场景 12-19"
echo "KF_HOME: $KF_HOME"
echo "============================================================"
echo ""

# 检查 master 是否运行
MASTER_PID=$(pgrep -f "kfc run.*master" | head -1)
if [ -z "$MASTER_PID" ]; then
    echo "错误: Master 进程未运行"
    echo "请先启动 master:"
    echo "  export KF_HOME=$KF_HOME"
    echo "  kfc run -c system -g master -n master &"
    exit 1
fi

echo "Master 进程 PID: $MASTER_PID"
echo ""

# 场景列表
SCENARIOS=(12 13 14 15 16 17 18 19)
TOTAL_SCENARIOS=${#SCENARIOS[@]}

# 统计变量
SUCCESS_COUNT=0
FAIL_COUNT=0
GLOBAL_START_TIME=$(date +%s)

echo "============================================================"
echo "开始运行 $TOTAL_SCENARIOS 个并行测试场景"
echo "============================================================"
echo ""

# 运行每个场景
for i in "${!SCENARIOS[@]}"; do
    SCENARIO_INDEX=${SCENARIOS[$i]}
    SCENARIO_START_TIME=$(date +%s)
    SCENARIO_START_FORMATTED=$(date '+%Y-%m-%d %H:%M:%S')

    # 进度条
    PROGRESS=$((i * 100 / TOTAL_SCENARIOS))
    printf "[$PROGRESS%%] "

    echo "============================================================"
    echo "场景 $SCENARIO_INDEX"
    echo "开始时间: $SCENARIO_START_FORMATTED"
    echo "============================================================"

    cd "$SCRIPT_DIR" || exit 1
    export KF_HOME="$KF_HOME"

    # 获取场景名称
    case $SCENARIO_INDEX in
        12) SCENARIO_NAME="P5_并行5_10文件" ;;
        13) SCENARIO_NAME="P10_并行10_10文件" ;;
        14) SCENARIO_NAME="P5_并行5_1000文件" ;;
        15) SCENARIO_NAME="P10_并行10_1000文件" ;;
        16) SCENARIO_NAME="P5_并行5_3000文件" ;;
        17) SCENARIO_NAME="P10_并行10_3000文件" ;;
        18) SCENARIO_NAME="P5_并行5_5000文件" ;;
        19) SCENARIO_NAME="P10_并行10_5000文件" ;;
    esac

    echo "场景: $SCENARIO_NAME"
    echo ""

    # 运行测试
    if $PYTHON "${SCRIPT_DIR}/perf_test_v2.py" --scenario "$SCENARIO_INDEX"; then
        SCENARIO_END_TIME=$(date +%s)
        SCENARIO_DURATION=$((SCENARIO_END_TIME - SCENARIO_START_TIME))

        # 格式化耗时
        if [ $SCENARIO_DURATION -ge 3600 ]; then
            DURATION_FORMATTED="$(printf '%02d' $((SCENARIO_DURATION / 3600)))h $(printf '%02d' $((SCENARIO_DURATION % 3600 / 60)))m $(printf '%02d' $((SCENARIO_DURATION % 60)))s"
        elif [ $SCENARIO_DURATION -ge 60 ]; then
            DURATION_FORMATTED="$(printf '%02d' $((SCENARIO_DURATION / 60)))m $(printf '%02d' $((SCENARIO_DURATION % 60)))s"
        else
            DURATION_FORMATTED="${SCENARIO_DURATION}s"
        fi

        echo "✓ 场景 $SCENARIO_INDEX ($SCENARIO_NAME) 完成"
        echo "  耗时: $DURATION_FORMATTED"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        SCENARIO_END_TIME=$(date +%s)
        SCENARIO_DURATION=$((SCENARIO_END_TIME - SCENARIO_START_TIME))

        echo "✗ 场景 $SCENARIO_INDEX ($SCENARIO_NAME) 失败"
        echo "  耗时: ${SCENARIO_DURATION}s (失败)"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi

    echo ""

    # 等待资源释放
    if [ $i -lt $((TOTAL_SCENARIOS - 1)) ]; then
        echo "等待 3 秒后继续..."
        echo ""
        sleep 3
    fi
done

GLOBAL_END_TIME=$(date +%s)
GLOBAL_DURATION=$((GLOBAL_END_TIME - GLOBAL_START_TIME))

# 格式化总耗时
if [ $GLOBAL_DURATION -ge 3600 ]; then
    TOTAL_DURATION_FORMATTED="$(printf '%02d' $((GLOBAL_DURATION / 3600)))h $(printf '%02d' $((GLOBAL_DURATION % 3600 / 60)))m $(printf '%02d' $((GLOBAL_DURATION % 60)))s"
elif [ $GLOBAL_DURATION -ge 60 ]; then
    TOTAL_DURATION_FORMATTED="$(printf '%02d' $((GLOBAL_DURATION / 60)))m $(printf '%02d' $((GLOBAL_DURATION % 60)))s"
else
    TOTAL_DURATION_FORMATTED="${GLOBAL_DURATION}s"
fi

# 输出汇总
echo "============================================================"
echo "测试完成！"
echo "============================================================"
echo "总场景数: $TOTAL_SCENARIOS"
echo "成功: $SUCCESS_COUNT"
echo "失败: $FAIL_COUNT"
echo "总耗时: $TOTAL_DURATION_FORMATTED"
echo "结果目录: $KF_HOME/test_results"
echo ""
echo "============================================================"
