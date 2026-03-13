#!/bin/bash
# 清理性能测试产生的临时文件

KF_HOME=${KF_HOME:-/Users/shandian/kungfu}

echo "============================================================"
echo "清理功夫性能测试临时文件"
echo "============================================================"

# 清理 journal 数据（占用最大）
JOURNAL_DIR="$KF_HOME/runtime/strategy/perf_test/app/journal/live"
if [ -d "$JOURNAL_DIR" ]; then
    FILE_COUNT=$(ls "$JOURNAL_DIR" 2>/dev/null | wc -l)
    if [ "$FILE_COUNT" -gt 0 ]; then
        echo "清理 journal 数据: $FILE_COUNT 个文件"
        rm -rf "$JOURNAL_DIR"/*
        echo "✓ journal 已清理"
    else
        echo "journal 目录为空，跳过"
    fi
else
    echo "journal 目录不存在，跳过"
fi

# 清理日志（可选）
LOG_DIR="$KF_HOME/runtime/strategy/perf_test/app/log/live"
if [ -d "$LOG_DIR" ]; then
    echo "清理日志文件..."
    rm -f "$LOG_DIR"/*
    echo "✓ 日志已清理"
fi

# 显示测试结果（不自动删除）
RESULT_DIR="$KF_HOME/test_results"
if [ -d "$RESULT_DIR" ]; then
    RESULT_COUNT=$(ls "$RESULT_DIR"/*.json 2>/dev/null | wc -l)
    echo ""
    echo "测试结果文件: $RESULT_COUNT 个"
    echo "目录: $RESULT_DIR"
    echo "如需清理旧结果，请手动删除"
fi

echo ""
echo "============================================================"
echo "清理完成！"
echo "============================================================"
