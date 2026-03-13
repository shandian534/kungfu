#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
"""
易筋经时间序列数据库性能测试脚本
基于 YIJINJING_PERFORMANCE_TEST_PLAN.md
"""

import os
import sys
import time
import psutil
import threading
import random
import glob
import json
from datetime import datetime
from multiprocessing import Process, Queue

import pandas as pd
import numpy as np

# 强制刷新输出，确保调试信息立即显示
sys.stdout.reconfigure(line_buffering=True)
print = lambda *args, **kwargs: __builtins__.print(*args, **kwargs, flush=True)

# 添加功夫核心库路径
kungfu_core_path = '/Users/shandian/out/kungfu/framework/core/build/python'
sys.path.insert(0, kungfu_core_path)

try:
    import pykungfu
    lf = pykungfu.longfist
    yjj = pykungfu.yijinjing
except ImportError as e:
    print(f"错误：无法导入功夫核心库: {e}")
    sys.exit(1)


# ============================================================================
# 数据选择器
# ============================================================================

class TradeDataSelector:
    """从真实交易数据目录中选择测试文件"""

    def __init__(self, trade_data_dir='/Users/shandian/kungfu/TRADE'):
        self.trade_data_dir = trade_data_dir
        self.all_files = sorted(glob.glob(os.path.join(trade_data_dir, '*.csv')))
        print(f"发现 {len(self.all_files)} 个CSV文件")

    def select_random_files(self, count):
        """随机选择指定数量的CSV文件"""
        if count > len(self.all_files):
            print(f"警告：请求 {count} 个文件，但只有 {len(self.all_files)} 个可用")
            count = len(self.all_files)

        selected_files = random.sample(self.all_files, count)
        print(f"随机选择了 {len(selected_files)} 个文件")
        return selected_files

    def select_sequential_files(self, count):
        """按顺序选择指定数量的CSV文件"""
        if count > len(self.all_files):
            print(f"警告：请求 {count} 个文件，但只有 {len(self.all_files)} 个可用")
            count = len(self.all_files)

        selected_files = self.all_files[:count]
        print(f"顺序选择了 {len(selected_files)} 个文件")
        return selected_files


def csv_to_quote(csv_row):
    """将交易数据CSV行转换为Quote对象"""
    quote = lf.types.Quote()

    # 转换为纳秒时间戳
    quote.data_time = int(csv_row['TIME']) * 1000000

    # 设置股票代码
    quote.instrument_id = str(int(csv_row['SYMBOL']))
    quote.exchange_id = "SSE"  # 交易所代码是字符串类型

    # 设置价格和数量
    quote.last_price = float(csv_row['PRICE'])
    quote.volume = int(csv_row['SIZE'])

    # 设置其他必要字段
    quote.open_interest = 0
    quote.bid_price = quote.last_price - 0.01
    quote.ask_price = quote.last_price + 0.01
    quote.bid_volume = 100
    quote.ask_volume = 100

    return quote


# ============================================================================
# 资源监控器
# ============================================================================

class ResourceMonitor:
    """资源监控器"""

    def __init__(self, interval=0.1):
        self.interval = interval
        self.running = False
        self.data = {'time': [], 'cpu': [], 'memory': []}
        self.process = psutil.Process()
        self.thread = None
        self.start_time = 0

    def start(self):
        """开始监控"""
        self.running = True
        self.start_time = time.time()
        self.thread = threading.Thread(target=self._monitor)
        self.thread.daemon = True
        self.thread.start()

    def _monitor(self):
        """监控线程"""
        while self.running:
            try:
                current_time = time.time() - self.start_time
                cpu_percent = self.process.cpu_percent()
                memory_info = self.process.memory_info()
                memory_percent = self.process.memory_percent()

                self.data['time'].append(current_time)
                self.data['cpu'].append(cpu_percent)
                self.data['memory'].append(memory_percent)

                time.sleep(self.interval)
            except Exception as e:
                print(f"[ResourceMonitor] 监控异常: {e}")
                break

    def stop(self):
        """停止监控"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)

    def get_data(self):
        """获取监控数据"""
        if not self.data['time']:
            return pd.DataFrame()
        return pd.DataFrame(self.data)


# ============================================================================
# 性能测试基类
# ============================================================================

class YijinjingPerformanceTest:
    """易筋经性能测试基类"""

    def __init__(self, test_name, kf_home=None):
        self.test_name = test_name

        # 处理 kf_home 路径
        if kf_home is None:
            kf_home = os.getenv('KF_HOME', '/Users/shandian/kungfu')
        if not kf_home.endswith('runtime'):
            kf_home = os.path.join(kf_home, 'runtime')
        self.kf_home = kf_home

        self.monitor = ResourceMonitor()
        self.apprentice = None

        # 测试结果
        self.results = {
            'test_name': test_name,
            'timestamp': datetime.now().isoformat(),
            'data_count': 0,
            'batch_size': 0,
            'parallel_count': 0,
            'total_time': 0,
            'total_rows': 0,
            'avg_latency_us': 0,
            'throughput_ops': 0,
            'resource_data': None
        }

    def setup_location(self, category='STRATEGY', group='perf_test', name='app'):
        """设置测试使用的 location"""
        locator = yjj.locator(self.kf_home)
        location = yjj.location(
            lf.enums.mode.LIVE,
            getattr(lf.enums.category, category),
            group,
            name,
            locator
        )
        return location, locator

    def save_results(self):
        """保存测试结果"""
        results_dir = os.path.join(os.path.dirname(self.kf_home), 'test_results')
        os.makedirs(results_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_file = os.path.join(results_dir, f'{self.test_name}_{timestamp}.json')

        # 转换 resource_data 为可序列化格式
        results = self.results.copy()
        if results['resource_data'] is not None and not results['resource_data'].empty:
            results['resource_data'] = results['resource_data'].to_dict('records')
        else:
            results['resource_data'] = []

        with open(result_file, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"结果已保存到: {result_file}")
        return result_file


# ============================================================================
# 顺序写入测试
# ============================================================================

class SequentialWriteTest(YijinjingPerformanceTest):
    """顺序写入测试"""

    def __init__(self, kf_home=None):
        super().__init__('sequential_write', kf_home)

    def run_test(self, csv_files, batch_size=1, parallel_count=1):
        """运行顺序写入测试"""
        file_count = len(csv_files)

        print(f"\n{'='*60}")
        print(f"=== 顺序写入测试 ===")
        print(f"CSV文件数: {file_count}, 批次大小: {batch_size}")
        print(f"{'='*60}")

        # 设置环境
        location, locator = self.setup_location()

        # 检查 master socket
        master_location = yjj.location(
            lf.enums.mode.LIVE,
            lf.enums.category.SYSTEM,
            'master',
            'master',
            locator
        )
        master_nn_path = locator.layout_file(master_location, lf.enums.layout.NANOMSG, 'pub')
        if not os.path.exists(master_nn_path):
            print(f"错误: Master socket 不存在: {master_nn_path}")
            print("请先启动 master: export KF_HOME=/Users/shandian/kungfu && kfc run -c system -g master -n master")
            return None

        # 创建 apprentice
        print("创建 apprentice...")
        self.apprentice = yjj.apprentice(location, low_latency=True)

        # 初始化
        print("初始化 apprentice...")
        try:
            self.apprentice.setup()
            print("Apprentice 注册成功!")
        except Exception as e:
            print(f"CRITICAL: Apprentice 初始化失败: {e}")
            return None

        # 获取 writer
        writer = self.apprentice.io_device.open_writer(0)

        # 开始监控
        print("开始资源监控...")
        self.monitor.start()

        # 执行写入
        print("开始写入数据...")
        start_time = time.time_ns()
        total_rows = 0

        for csv_file in csv_files:
            df = pd.read_csv(csv_file)
            for _, row in df.iterrows():
                quote = csv_to_quote(row)
                writer.write(time.time_ns(), quote)
                total_rows += 1

            # 每处理100个文件输出进度
            if (csv_files.index(csv_file) + 1) % 100 == 0:
                processed = csv_files.index(csv_file) + 1
                print(f"已处理: {processed}/{file_count} 文件")

        end_time = time.time_ns()

        # 停止监控
        self.monitor.stop()

        # 计算指标
        total_time_s = (end_time - start_time) / 1e9
        avg_latency_us = (end_time - start_time) / total_rows / 1000 if total_rows > 0 else 0
        throughput_ops = total_rows / total_time_s if total_time_s > 0 else 0

        # 记录结果
        self.results.update({
            'data_count': file_count,
            'batch_size': batch_size,
            'parallel_count': 1,
            'total_time': total_time_s,
            'total_rows': total_rows,
            'avg_latency_us': avg_latency_us,
            'throughput_ops': throughput_ops,
            'resource_data': self.monitor.get_data()
        })

        # 打印结果
        print(f"\n{'='*60}")
        print(f"测试结果:")
        print(f"  总行数: {total_rows}")
        print(f"  总耗时: {total_time_s:.2f}秒")
        print(f"  吞吐量: {throughput_ops:.0f} ops")
        print(f"  平均延迟: {avg_latency_us:.2f}微秒")
        print(f"{'='*60}\n")

        return self.results


# ============================================================================
# 并行写入测试
# ============================================================================

class ParallelWriteTest(YijinjingPerformanceTest):
    """并行写入测试"""

    def __init__(self, kf_home=None):
        super().__init__('parallel_write', kf_home)

    def worker_process(self, worker_id, csv_files, result_queue, kf_home):
        """工作进程"""
        try:
            # 设置进程内的 kf_home
            if not kf_home.endswith('runtime'):
                kf_home = os.path.join(kf_home, 'runtime')

            # 每个进程创建独立的 location
            locator = yjj.locator(kf_home)
            location = yjj.location(
                lf.enums.mode.LIVE,
                lf.enums.category.STRATEGY,
                'perf_test',
                f'worker_{worker_id}',
                locator
            )

            # 创建 apprentice
            apprentice = yjj.apprentice(location, low_latency=True)
            apprentice.setup()

            writer = apprentice.io_device.open_writer(0)

            # 执行写入并测量
            start_time = time.time_ns()
            total_rows = 0

            for csv_file in csv_files:
                df = pd.read_csv(csv_file)
                for _, row in df.iterrows():
                    quote = csv_to_quote(row)
                    writer.write(time.time_ns(), quote)
                    total_rows += 1

            end_time = time.time_ns()

            total_time_s = (end_time - start_time) / 1e9
            avg_latency_us = (end_time - start_time) / total_rows / 1000 if total_rows > 0 else 0
            throughput_ops = total_rows / total_time_s if total_time_s > 0 else 0

            result_queue.put({
                'worker_id': worker_id,
                'total_time': total_time_s,
                'total_rows': total_rows,
                'avg_latency_us': avg_latency_us,
                'throughput_ops': throughput_ops
            })

        except Exception as e:
            result_queue.put({'worker_id': worker_id, 'error': str(e)})

    def run_test(self, csv_files, batch_size=1, parallel_count=5):
        """运行并行写入测试"""
        file_count = len(csv_files)

        print(f"\n{'='*60}")
        print(f"=== 并行写入测试 ===")
        print(f"CSV文件数: {file_count}, 并行数: {parallel_count}")
        print(f"{'='*60}")

        # 分配CSV文件给各个进程
        files_per_worker = len(csv_files) // parallel_count
        worker_files = []

        for i in range(parallel_count):
            start_idx = i * files_per_worker
            if i == parallel_count - 1:
                end_idx = len(csv_files)
            else:
                end_idx = start_idx + files_per_worker
            worker_files.append(csv_files[start_idx:end_idx])

        # 使用原始 kf_home (不带 runtime)
        base_kf_home = self.kf_home.replace('/runtime', '') if self.kf_home.endswith('runtime') else self.kf_home

        # 开始监控
        print("开始资源监控...")
        self.monitor.start()

        # 创建进程池
        result_queue = Queue()
        processes = []

        print(f"启动 {parallel_count} 个工作进程...")
        for i in range(parallel_count):
            p = Process(
                target=self.worker_process,
                args=(i, worker_files[i], result_queue, base_kf_home)
            )
            processes.append(p)
            p.start()

        # 等待所有进程完成
        print("等待所有进程完成...")
        for p in processes:
            p.join()

        # 停止监控
        self.monitor.stop()

        # 收集结果
        results = []
        while not result_queue.empty():
            results.append(result_queue.get())

        # 检查错误
        errors = [r for r in results if 'error' in r]
        if errors:
            print(f"警告: {len(errors)} 个进程失败:")
            for e in errors:
                print(f"  Worker {e['worker_id']}: {e['error']}")

        # 过滤成功的结果
        success_results = [r for r in results if 'error' not in r]
        if not success_results:
            print("错误: 所有工作进程都失败了")
            return None

        # 计算总体指标
        total_ops = sum(r.get('throughput_ops', 0) for r in success_results)
        total_rows_all = sum(r.get('total_rows', 0) for r in success_results)
        max_time = max(r.get('total_time', 0) for r in success_results)
        avg_latency = sum(r.get('avg_latency_us', 0) for r in success_results) / len(success_results)

        self.results.update({
            'data_count': file_count,
            'batch_size': batch_size,
            'parallel_count': parallel_count,
            'total_time': max_time,
            'total_rows': total_rows_all,
            'avg_latency_us': avg_latency,
            'throughput_ops': total_ops,
            'resource_data': self.monitor.get_data(),
            'worker_results': success_results
        })

        # 打印结果
        print(f"\n{'='*60}")
        print(f"测试结果:")
        print(f"  总行数: {total_rows_all}")
        print(f"  总耗时: {max_time:.2f}秒")
        print(f"  总吞吐量: {total_ops:.0f} ops")
        print(f"  平均延迟: {avg_latency:.2f}微秒")
        print(f"  成功工作进程: {len(success_results)}/{parallel_count}")
        print(f"{'='*60}\n")

        return self.results


# ============================================================================
# 测试场景配置
# ============================================================================

TEST_SCENARIOS = [
    # (场景名称, CSV文件数, 批次大小, 并行数, 测试类型)
    ('S1_快速验证', 10, 1, 1, 'sequential'),
    ('S2_顺序写入_小批量', 100, 1, 1, 'sequential'),
    ('S3_顺序写入_中批量', 100, 10, 1, 'sequential'),
    ('S4_顺序写入_大批量', 100, 50, 1, 'sequential'),
    ('S5_并行写入_5进程', 100, 1, 5, 'parallel'),
    ('S6_并行写入_10进程', 100, 1, 10, 'parallel'),
    # 大规模测试需要较多时间，可选
    # ('S7_大规模并行', 1000, 100, 5, 'parallel'),
    # ('S8_超大规模并行', 1000, 100, 10, 'parallel'),
]


# ============================================================================
# 主测试流程
# ============================================================================

def run_single_scenario(scenario_name, file_count, batch_size, parallel_count, mode, csv_files, kf_home, result_queue):
    """运行单个场景（在子进程中）"""
    try:
        # 在子进程中重新导入模块，因为功夫的限制
        import sys
        sys.path.insert(0, '/Users/shandian/out/kungfu/framework/core/build/python')
        import pykungfu
        lf = pykungfu.longfist
        yjj = pykungfu.yijinjing
        import pandas as pd
        import time
        import os

        # 获取对应数量的CSV文件
        csv_files = csv_files[:file_count]

        if mode == 'sequential':
            test = SequentialWriteTest(kf_home)
        else:
            test = ParallelWriteTest(kf_home)

        result = test.run_test(csv_files, batch_size, parallel_count)

        if result:
            result['scenario_name'] = scenario_name
            # 保存单次结果
            test.save_results()

        result_queue.put(('success', result))

    except Exception as e:
        result_queue.put(('error', (scenario_name, str(e))))

    finally:
        # 清理 apprentice
        if 'test' in locals() and test.apprentice is not None:
            try:
                del test.apprentice
            except:
                pass


def run_all_tests(scenario_indices=None, kf_home='/Users/shandian/kungfu'):
    """运行所有测试场景"""
    print("=" * 60)
    print("易筋经时间序列数据库性能测试")
    print("=" * 60)

    # 过滤要运行的场景
    if scenario_indices is not None:
        scenarios = [TEST_SCENARIOS[i] for i in scenario_indices if i < len(TEST_SCENARIOS)]
    else:
        scenarios = TEST_SCENARIOS

    # 使用真实交易数据
    trade_data_dir = os.path.join(kf_home, 'TRADE')
    if not os.path.exists(trade_data_dir):
        print(f"错误: 交易数据目录不存在: {trade_data_dir}")
        return []

    selector = TradeDataSelector(trade_data_dir)

    # 找出最大文件数
    max_file_count = max(s[1] for s in scenarios)

    # 顺序选择所需数量的CSV文件（保证测试一致性）
    print(f"\n从 {trade_data_dir} 选择测试数据...")
    selected_files = selector.select_sequential_files(max_file_count)
    print(f"已选择 {len(selected_files)} 个文件用于测试\n")

    all_results = []
    results_dir = os.path.join(kf_home, 'test_results')
    os.makedirs(results_dir, exist_ok=True)

    for scenario_name, file_count, batch_size, parallel_count, mode in scenarios:
        print(f"\n{'#'*60}")
        print(f"# 运行场景: {scenario_name}")
        print(f"{'#'*60}")

        # 使用子进程运行每个场景（因为每个进程只能有一个 hero 实例）
        result_queue = Queue()
        p = Process(
            target=run_single_scenario,
            args=(scenario_name, file_count, batch_size, parallel_count, mode, selected_files, kf_home, result_queue)
        )
        p.start()
        p.join()

        # 获取结果
        if not result_queue.empty():
            status, data = result_queue.get()
            if status == 'success' and data:
                all_results.append(data)
            elif status == 'error':
                print(f"测试失败: {data[1]}")

        # 短暂休息，避免资源占用
        time.sleep(2)

    # 生成汇总报告
    if all_results:
        generate_summary_report(all_results, results_dir)

    print("\n" + "=" * 60)
    print(f"测试完成! 共完成 {len(all_results)} 个场景")
    print(f"结果目录: {results_dir}")
    print("=" * 60)

    return all_results


def generate_summary_report(results, output_dir):
    """生成汇总报告"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    summary_file = os.path.join(output_dir, f'test_summary_{timestamp}.csv')

    # 生成汇总表格
    summary_data = []
    for r in results:
        summary_data.append({
            '场景名称': r.get('scenario_name', r['test_name']),
            '数据量(CSV)': r['data_count'],
            '总行数': r['total_rows'],
            '批次大小': r['batch_size'],
            '并行数': r['parallel_count'],
            '总耗时(秒)': f"{r['total_time']:.2f}",
            '平均延迟(微秒)': f"{r['avg_latency_us']:.2f}",
            '吞吐量(ops)': f"{r['throughput_ops']:.0f}"
        })

    df = pd.DataFrame(summary_data)
    df.to_csv(summary_file, index=False, encoding='utf-8-sig')
    print(f"\n汇总表格已保存: {summary_file}")

    # 打印汇总到控制台
    print("\n" + "=" * 80)
    print("测试结果汇总:")
    print("=" * 80)
    print(df.to_string(index=False))
    print("=" * 80)


# ============================================================================
# 快速测试
# ============================================================================

def quick_test(kf_home='/Users/shandian/kungfu'):
    """快速测试 - 验证环境和数据"""
    print("=" * 60)
    print("快速环境验证测试")
    print("=" * 60)

    trade_data_dir = os.path.join(kf_home, 'TRADE')
    if not os.path.exists(trade_data_dir):
        print(f"错误: 交易数据目录不存在: {trade_data_dir}")
        return None

    selector = TradeDataSelector(trade_data_dir)
    csv_files = selector.select_random_files(10)

    # 显示选择的文件信息
    print("\n选择的文件（前3个）:")
    for f in csv_files[:3]:
        file_size = os.path.getsize(f)
        print(f"  {os.path.basename(f)} ({file_size} bytes)")

    test = SequentialWriteTest(kf_home)
    result = test.run_test(csv_files, batch_size=1)

    if result:
        print("\n快速测试完成，环境验证成功！")
        test.save_results()

    return result


# ============================================================================
# 主入口
# ============================================================================

def main():
    """主入口"""
    import argparse

    parser = argparse.ArgumentParser(description='易筋经性能测试')
    parser.add_argument('--mode', choices=['quick', 'scenario'], default='scenario',
                        help='测试模式: quick(快速验证), scenario(指定单个场景)')
    parser.add_argument('--scenario', type=int, default=0,
                        help='场景索引: 0=快速验证(10文件), 1=小批量(100文件), 2=中批量, 3=大批量, 4=并行5进程, 5=并行10进程')
    parser.add_argument('--kf-home', type=str, default='/Users/shandian/kungfu',
                        help='KF_HOME 路径')

    args = parser.parse_args()

    if args.mode == 'quick':
        quick_test(args.kf_home)
    else:  # scenario
        # 每次只运行一个场景
        if args.scenario >= len(TEST_SCENARIOS):
            print(f"错误: 场景索引 {args.scenario} 不存在，最大为 {len(TEST_SCENARIOS) - 1}")
            return

        scenario_name, file_count, batch_size, parallel_count, mode = TEST_SCENARIOS[args.scenario]
        print(f"\n将运行场景 {args.scenario}: {scenario_name}")
        print(f"  文件数: {file_count}, 批次: {batch_size}, 并行: {parallel_count}, 类型: {mode}")

        # 准备数据
        trade_data_dir = os.path.join(args.kf_home, 'TRADE')
        if not os.path.exists(trade_data_dir):
            print(f"错误: 交易数据目录不存在: {trade_data_dir}")
            return

        selector = TradeDataSelector(trade_data_dir)
        selected_files = selector.select_sequential_files(file_count)

        # 运行单个场景
        if mode == 'sequential':
            test = SequentialWriteTest(args.kf_home)
        else:
            test = ParallelWriteTest(args.kf_home)

        result = test.run_test(selected_files, batch_size, parallel_count)

        if result:
            result['scenario_name'] = scenario_name
            test.save_results()
            print(f"\n场景 '{scenario_name}' 完成！")


if __name__ == '__main__':
    main()
