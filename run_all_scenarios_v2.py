#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
"""
批量运行所有性能测试场景 V2
"""

import os
import sys
import time
import subprocess
import json
from datetime import datetime, timedelta

# 强制刷新输出
sys.stdout.reconfigure(line_buffering=True)
print = lambda *args, **kwargs: __builtins__.print(*args, **kwargs, flush=True)


# 所有场景配置
TEST_SCENARIOS = [
    # (索引, 场景名称)
    (0, 'S1_顺序_10文件'),
    (1, 'S2_顺序_1000文件'),
    (2, 'S3_顺序_3000文件'),
    (3, 'S4_顺序_5000文件'),
    (4, 'B10_批量10_10文件'),
    (5, 'B100_批量100_10文件'),
    (6, 'B10_批量10_1000文件'),
    (7, 'B100_批量100_1000文件'),
    (8, 'B10_批量10_3000文件'),
    (9, 'B100_批量100_3000文件'),
    (10, 'B10_批量10_5000文件'),
    (11, 'B100_批量100_5000文件'),
    (12, 'P5_并行5_10文件'),
    (13, 'P10_并行10_10文件'),
    (14, 'P5_并行5_1000文件'),
    (15, 'P10_并行10_1000文件'),
    (16, 'P5_并行5_3000文件'),
    (17, 'P10_并行10_3000文件'),
    (18, 'P5_并行5_5000文件'),
    (19, 'P10_并行10_5000文件'),
]

KF_HOME = os.getenv('KF_HOME', '/Users/shandian/kungfu')
PYTHON = '/usr/local/bin/python3.9'
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def format_duration(seconds):
    """格式化耗时"""
    if seconds >= 3600:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}h {minutes:02d}m {secs:02d}s"
    elif seconds >= 60:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}m {secs:02d}s"
    else:
        return f"{int(seconds)}s"


def check_master():
    """检查 master 是否运行"""
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'kfc run.*master'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip().split('\n')[0]
        return None
    except Exception as e:
        print(f"检查 master 时出错: {e}")
        return None


def run_scenario(index, name):
    """运行单个场景"""
    start_time = time.time()
    start_formatted = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    print(f"开始时间: {start_formatted}")

    # 运行测试脚本
    script_path = os.path.join(SCRIPT_DIR, 'perf_test_v2.py')
    cmd = [PYTHON, script_path, '--scenario', str(index)]

    env = os.environ.copy()
    env['KF_HOME'] = KF_HOME

    try:
        result = subprocess.run(
            cmd,
            env=env,
            cwd=SCRIPT_DIR,
            capture_output=True,
            text=True
        )

        end_time = time.time()
        duration = end_time - start_time
        duration_formatted = format_duration(duration)

        if result.returncode == 0:
            print(f"✓ 场景 {index} ({name}) 完成")
            print(f"  耗时: {duration_formatted}")
            return True, duration, duration_formatted
        else:
            print(f"✗ 场景 {index} ({name}) 失败")
            print(f"  耗时: {duration_formatted} (失败)")
            if result.stderr:
                print(f"  错误: {result.stderr[:200]}")
            return False, duration, duration_formatted

    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        print(f"✗ 场景 {index} ({name}) 异常")
        print(f"  耗时: {format_duration(duration)}")
        print(f"  异常: {e}")
        return False, duration, format_duration(duration)


def main():
    """主函数"""
    print("=" * 60)
    print("易筋经性能测试 V2 - 批量运行")
    print(f"KF_HOME: {KF_HOME}")
    print("=" * 60)
    print()

    # 检查 master
    master_pid = check_master()
    if not master_pid:
        print("错误: Master 进程未运行")
        print("请先启动 master:")
        print("  export KF_HOME=/Users/shandian/kungfu")
        print("  kfc run -c system -g master -n master &")
        sys.exit(1)

    print(f"Master 进程 PID: {master_pid}")
    print()

    # 统计变量
    total_scenarios = len(TEST_SCENARIOS)
    results = []
    global_start = time.time()

    print("=" * 60)
    print(f"开始运行 {total_scenarios} 个测试场景")
    print("=" * 60)
    print()

    # 运行每个场景
    for i, (index, name) in enumerate(TEST_SCENARIOS):
        # 进度显示
        progress = i * 100 // total_scenarios
        print(f"[{progress:3d}%] ", end='')

        print("=" * 60)
        print(f"场景 {index}/{total_scenarios-1}: {name}")
        print("=" * 60)

        success, duration, duration_formatted = run_scenario(index, name)
        results.append({
            'index': index,
            'name': name,
            'success': success,
            'duration': duration,
            'duration_formatted': duration_formatted
        })

        print()

        # 等待资源释放
        if i < total_scenarios - 1:
            print("等待 3 秒后继续...")
            print()
            time.sleep(3)

    global_end = time.time()
    global_duration = global_end - global_start

    # 统计结果
    success_count = sum(1 for r in results if r['success'])
    fail_count = sum(1 for r in results if not r['success'])

    # 输出汇总
    print("=" * 60)
    print("测试完成！")
    print("=" * 60)
    print(f"总场景数: {total_scenarios}")
    print(f"成功: {success_count}")
    print(f"失败: {fail_count}")
    print(f"总耗时: {format_duration(global_duration)}")
    print(f"结果目录: {KF_HOME}/test_results")
    print()

    # 详细结果表格
    print("=" * 60)
    print("场景结果汇总")
    print("=" * 60)
    print(f"{'索引':<5} {'场景名称':<35} {'状态':<8} {'耗时':>10}")
    print("-" * 60)

    for r in results:
        status = "✓" if r['success'] else "✗"
        print(f"{r['index']:<5} {r['name']:<35} {status:<8} {r['duration_formatted']:>10}")

    print()

    # 按类型分组统计
    print("=" * 60)
    print("按类型统计")
    print("=" * 60)

    print("\n【顺序写入】")
    for r in results[0:4]:
        status = "✓" if r['success'] else "✗"
        print(f"  场景 {r['index']}: {r['name']} - {status} - {r['duration_formatted']}")

    print("\n【批量写入】")
    for r in results[4:12]:
        status = "✓" if r['success'] else "✗"
        print(f"  场景 {r['index']}: {r['name']} - {status} - {r['duration_formatted']}")

    print("\n【并行写入】")
    for r in results[12:20]:
        status = "✓" if r['success'] else "✗"
        print(f"  场景 {r['index']}: {r['name']} - {status} - {r['duration_formatted']}")

    print("=" * 60)


if __name__ == '__main__':
    main()
