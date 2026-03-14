#!/bin/bash
# 运行顺序写入和批量写入测试场景 (0-11)

KF_HOME=${KF_HOME:-/Users/shandian/kungfu}
PYTHON=${PYTHON:-/usr/local/bin/python3.9}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================================"
echo "顺序和批量性能测试 - 场景 0-11"
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
SCENARIOS=(
    "0|S1_顺序_10文件"
    "1|S2_顺序_1000文件"
    "2|S3_顺序_3000文件"
    "3|S4_顺序_5000文件"
    "4|B10_批量10_10文件"
    "5|B100_批量100_10文件"
    "6|B10_批量10_1000文件"
    "7|B100_批量100_1000文件"
    "8|B10_批量10_3000文件"
    "9|B100_批量100_3000文件"
    "10|B10_批量10_5000文件"
    "11|B100_批量100_5000文件"
)

TOTAL_SCENARIOS=${#SCENARIOS[@]}

# 统计变量
SUCCESS_COUNT=0
FAIL_COUNT=0
GLOBAL_START_TIME=$(date +%s)

echo "============================================================"
echo "开始运行 $TOTAL_SCENARIOS 个测试场景"
echo "============================================================"
echo ""

# 运行每个场景
for i in "${!SCENARIOS[@]}"; do
    IFS='|' read -r index name <<< "${SCENARIOS[$i]}"

    SCENARIO_START_TIME=$(date +%s)
    SCENARIO_START_FORMATTED=$(date '+%Y-%m-%d %H:%M:%S')

    # 进度条
    PROGRESS=$((i * 100 / TOTAL_SCENARIOS))
    printf "[$PROGRESS%%] "

    echo "============================================================"
    echo "场景 $index/$((TOTAL_SCENARIOS-1)): $name"
    echo "开始时间: $SCENARIO_START_FORMATTED"
    echo "============================================================"

    cd "$SCRIPT_DIR" || exit 1
    export KF_HOME="$KF_HOME"

    # 运行测试
    if $PYTHON "${SCRIPT_DIR}/perf_test_v2.py" --scenario "$index"; then
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

        echo "✓ 场景 $index ($name) 完成"
        echo "  耗时: $DURATION_FORMATTED"
        RESULTS[$i]="✓"
        TIMES[$i]="$SCENARIO_DURATION"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        SCENARIO_END_TIME=$(date +%s)
        SCENARIO_DURATION=$((SCENARIO_END_TIME - SCENARIO_START_TIME))

        echo "✗ 场景 $index ($name) 失败"
        echo "  耗时: ${SCENARIO_DURATION}s (失败)"
        RESULTS[$i]="✗"
        TIMES[$i]="$SCENARIO_DURATION"
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

# 详细结果表格
echo "============================================================"
echo "场景结果汇总"
echo "============================================================"
printf "%-5s %-35s %-10s %s\n" "索引" "场景名称" "状态" "耗时"
echo "------------------------------------------------------------"

for i in "${!TIMES[@]}"; do
    IFS='|' read -r index name <<< "${SCENARIOS[$i]}"
    DURATION=${TIMES[$i]}
    STATUS=${RESULTS[$i]}

    # 格式化单个场景耗时
    if [ $DURATION -ge 60 ]; then
        DUR_FMT="$(printf '%02d' $((DURATION / 60)))m $(printf '%02d' $((DURATION % 60)))s"
    else
        DUR_FMT="${DURATION}s"
    fi

    printf "%-5s %-35s %-10s %s\n" "$index" "$name" "$STATUS" "$DUR_FMT"
done

echo ""

# 按类型分组统计
echo "============================================================"
echo "按类型统计"
echo "============================================================"

echo ""
echo "【顺序写入】"
for i in 0 1 2 3; do
    IFS='|' read -r index name <<< "${SCENARIOS[$i]}"
    DURATION=${TIMES[$i]}
    if [ $DURATION -ge 60 ]; then
        DUR_FMT="$(printf '%02d' $((DURATION / 60)))m $(printf '%02d' $((DURATION % 60)))s"
    else
        DUR_FMT="${DURATION}s"
    fi
    echo "  场景 $index: $name - ${RESULTS[$i]} - $DUR_FMT"
done

echo ""
echo "【批量写入】"
for i in 4 5 6 7 8 9 10 11; do
    IFS='|' read -r index name <<< "${SCENARIOS[$i]}"
    DURATION=${TIMES[$i]}
    if [ $DURATION -ge 60 ]; then
        DUR_FMT="$(printf '%02d' $((DURATION / 60)))m $(printf '%02d' $((DURATION % 60)))s"
    else
        DUR_FMT="${DURATION}s"
    fi
    echo "  场景 $index: $name - ${RESULTS[$i]} - $DUR_FMT"
done

echo "============================================================"
