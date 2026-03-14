#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
"""
易筋经时间序列数据库性能测试脚本 V2
按文件级别的批处理逻辑：
- 顺序写入：1个文件→处理完成→下1个文件
- 批量写入：10个文件→一起处理→下10个文件
- 并行写入：5个进程，每个进程同时处理1个文件
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
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# 强制刷新输出
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
# 数据转换
# ============================================================================

def csv_to_quote(csv_row):
    """将交易数据CSV行转换为Quote对象"""
    quote = lf.types.Quote()
    quote.data_time = int(csv_row['TIME']) * 1000000
    quote.instrument_id = str(csv_row['SYMBOL'])
    quote.last_price = float(csv_row['PRICE'])
    return quote


# ============================================================================
# 数据选择器
# ============================================================================

class TradeDataSelector:
    """从真实交易数据目录中选择测试文件"""

    def __init__(self, trade_data_dir='/Users/shandian/kungfu/TRADE'):
        self.trade_data_dir = trade_data_dir
        self.all_files = sorted(glob.glob(os.path.join(trade_data_dir, '*.csv')))
        print(f"发现 {len(self.all_files)} 个CSV文件")

    def select_sequential_files(self, count):
        """按顺序选择指定数量的CSV文件"""
        if count > len(self.all_files):
            print(f"警告：请求 {count} 个文件，但只有 {len(self.all_files)} 个可用")
            count = len(self.all_files)

        selected_files = self.all_files[:count]
        print(f"顺序选择了 {len(selected_files)} 个文件")
        return selected_files


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
# 基础测试类
# ============================================================================

class BasePerformanceTest:
    """性能测试基类"""

    def __init__(self, test_name, kf_home=None):
        self.test_name = test_name

        if kf_home is None:
            kf_home = os.getenv('KF_HOME', '/Users/shandian/kungfu')
        if not kf_home.endswith('runtime'):
            kf_home = os.path.join(kf_home, 'runtime')
        self.kf_home = kf_home

        self.monitor = ResourceMonitor()
        self.apprentice = None

        self.results = {
            'test_name': test_name,
            'timestamp': datetime.now().isoformat(),
            'data_count': 0,
            'batch_size': 0,
            'parallel_count': 0,
            'total_time': 0,
            'parse_time': 0,
            'write_time': 0,
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

        results = self.results.copy()
        resource_data = None
        if results['resource_data'] is not None and not results['resource_data'].empty:
            resource_data = results['resource_data'].copy()
            results['resource_data'] = results['resource_data'].to_dict('records')
        else:
            results['resource_data'] = []

        with open(result_file, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"结果已保存到: {result_file}")

        # 生成资源监控图表
        if resource_data is not None and not resource_data.empty:
            chart_file = self._save_resource_chart(resource_data, results_dir, timestamp)
            if chart_file:
                print(f"资源监控图表已保存到: {chart_file}")

        return result_file

    def _save_resource_chart(self, resource_data, results_dir, timestamp):
        """保存资源监控图表"""
        try:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

            ax1.plot(resource_data['time'], resource_data['cpu'], 'r-', label='usage of CPU(%)')
            ax1.set_ylabel('usage of CPU (%)')
            ax1.grid(True, alpha=0.3)
            legend1 = ax1.legend(loc='upper right')
            plt.setp(legend1.get_texts(), color='red')

            ax2.plot(resource_data['time'], resource_data['memory'], 'b-', label='usage of memory(%)')
            ax2.set_xlabel('time (s)')
            ax2.set_ylabel('usage of memory (%)')
            ax2.grid(True, alpha=0.3)
            legend2 = ax2.legend(loc='upper right')
            plt.setp(legend2.get_texts(), color='blue')

            cpu_avg = resource_data['cpu'].mean()
            cpu_max = resource_data['cpu'].max()

            ax1.text(0.02, 0.98, f'Avg: {cpu_avg:.1f}% | Max: {cpu_max:.1f}%',
                    transform=ax1.transAxes, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

            plt.tight_layout()

            chart_file = os.path.join(results_dir, f'{self.test_name}_{timestamp}.png')
            plt.savefig(chart_file, dpi=150, bbox_inches='tight')
            plt.close(fig)

            return chart_file

        except Exception as e:
            print(f"生成图表时出错: {e}")
            return None


# ============================================================================
# 顺序写入测试（每次处理1个文件）
# ============================================================================

class SequentialWriteTest(BasePerformanceTest):
    """顺序写入测试：每次处理1个文件"""

    def __init__(self, kf_home=None):
        super().__init__('sequential_write', kf_home)

    def run_test(self, csv_files):
        """运行顺序写入测试"""
        file_count = len(csv_files)

        print(f"\n{'='*60}")
        print(f"=== 顺序写入测试 ===")
        print(f"CSV文件数: {file_count}, 每次处理: 1个文件")
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
            print("请先启动 master")
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

        writer = self.apprentice.io_device.open_writer(0)

        # 开始监控
        print("开始资源监控...")
        self.monitor.start()

        # 执行写入（每次处理1个文件）
        print(f"开始写入数据... (每次处理1个文件)")

        parse_time_ns = 0
        write_time_ns = 0
        total_rows = 0

        for i, csv_file in enumerate(csv_files, 1):
            # 解析单个文件
            parse_start = time.time_ns()
            df = pd.read_csv(csv_file)
            quotes = []
            for _, row in df.iterrows():
                quotes.append(csv_to_quote(row))
            parse_end = time.time_ns()
            parse_time_ns += (parse_end - parse_start)

            # 写入单个文件
            write_start = time.time_ns()
            current_time = time.time_ns()
            for quote in quotes:
                writer.write(current_time, quote)
                total_rows += 1
            write_end = time.time_ns()
            write_time_ns += (write_end - write_start)

            # 每处理100个文件输出进度
            if i % 100 == 0:
                print(f"已处理: {i}/{file_count} 文件")

        # 停止监控
        self.monitor.stop()

        # 计算指标
        parse_time_s = parse_time_ns / 1e9
        write_time_s = write_time_ns / 1e9
        total_time_s = parse_time_s + write_time_s
        avg_latency_us = write_time_ns / total_rows / 1000 if total_rows > 0 else 0
        throughput_ops = total_rows / total_time_s if total_time_s > 0 else 0

        self.results.update({
            'data_count': file_count,
            'batch_size': 1,
            'parallel_count': 1,
            'total_time': total_time_s,
            'parse_time': parse_time_s,
            'write_time': write_time_s,
            'total_rows': total_rows,
            'avg_latency_us': avg_latency_us,
            'throughput_ops': throughput_ops,
            'resource_data': self.monitor.get_data()
        })

        # 打印结果
        print(f"\n{'='*60}")
        print(f"测试结果:")
        print(f"  总行数: {total_rows}")
        print(f"  CSV解析时间: {parse_time_s:.2f}秒 ({parse_time_s/total_time_s*100:.1f}%)")
        print(f"  数据库写入时间: {write_time_s:.2f}秒 ({write_time_s/total_time_s*100:.1f}%)")
        print(f"  总耗时: {total_time_s:.2f}秒")
        print(f"  吞吐量: {throughput_ops:.0f} ops")
        print(f"  平均延迟: {avg_latency_us:.2f}微秒")
        print(f"{'='*60}\n")

        return self.results


# ============================================================================
# 批量写入测试（每次处理N个文件）
# ============================================================================

class BatchWriteTest(BasePerformanceTest):
    """批量写入测试：每次同时处理N个文件"""

    def __init__(self, kf_home=None):
        super().__init__('batch_write', kf_home)

    def run_test(self, csv_files, batch_size=10):
        """运行批量写入测试"""
        file_count = len(csv_files)

        print(f"\n{'='*60}")
        print(f"=== 批量写入测试 ===")
        print(f"CSV文件数: {file_count}, 每次处理: {batch_size}个文件")
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

        writer = self.apprentice.io_device.open_writer(0)

        # 开始监控
        print("开始资源监控...")
        self.monitor.start()

        # 执行写入（每次处理N个文件）
        print(f"开始写入数据... (每次处理{batch_size}个文件)")

        parse_time_ns = 0
        write_time_ns = 0
        total_rows = 0
        processed = 0

        while processed < file_count:
            # 确定本批次文件
            batch_files = csv_files[processed:processed + batch_size]
            batch_count = len(batch_files)

            # 解析批次中所有文件
            parse_start = time.time_ns()
            all_quotes = []
            for csv_file in batch_files:
                df = pd.read_csv(csv_file)
                for _, row in df.iterrows():
                    all_quotes.append(csv_to_quote(row))
            parse_end = time.time_ns()
            parse_time_ns += (parse_end - parse_start)

            # 写入批次中所有数据
            write_start = time.time_ns()
            current_time = time.time_ns()
            for quote in all_quotes:
                writer.write(current_time, quote)
                total_rows += 1
            write_end = time.time_ns()
            write_time_ns += (write_end - write_start)

            processed += batch_count
            print(f"已处理: {processed}/{file_count} 文件 (本批次: {batch_count}个)")

        # 停止监控
        self.monitor.stop()

        # 计算指标
        parse_time_s = parse_time_ns / 1e9
        write_time_s = write_time_ns / 1e9
        total_time_s = parse_time_s + write_time_s
        avg_latency_us = write_time_ns / total_rows / 1000 if total_rows > 0 else 0
        throughput_ops = total_rows / total_time_s if total_time_s > 0 else 0

        self.results.update({
            'data_count': file_count,
            'batch_size': batch_size,
            'parallel_count': 1,
            'total_time': total_time_s,
            'parse_time': parse_time_s,
            'write_time': write_time_s,
            'total_rows': total_rows,
            'avg_latency_us': avg_latency_us,
            'throughput_ops': throughput_ops,
            'resource_data': self.monitor.get_data()
        })

        # 打印结果
        print(f"\n{'='*60}")
        print(f"测试结果:")
        print(f"  总行数: {total_rows}")
        print(f"  CSV解析时间: {parse_time_s:.2f}秒 ({parse_time_s/total_time_s*100:.1f}%)")
        print(f"  数据库写入时间: {write_time_s:.2f}秒 ({write_time_s/total_time_s*100:.1f}%)")
        print(f"  总耗时: {total_time_s:.2f}秒")
        print(f"  吞吐量: {throughput_ops:.0f} ops")
        print(f"  平均延迟: {avg_latency_us:.2f}微秒")
        print(f"{'='*60}\n")

        return self.results


# ============================================================================
# 并行写入测试（多进程，每个进程处理1个文件）
# ============================================================================

def parallel_worker_process(worker_id, csv_files, result_queue, kf_home):
    """并行工作进程（每个进程处理分配的文件）"""
    try:
        # 重新导入模块
        import sys
        sys.path.insert(0, '/Users/shandian/out/kungfu/framework/core/build/python')
        import pykungfu
        lf = pykungfu.longfist
        yjj = pykungfu.yijinjing
        import pandas as pd
        import time
        import os

        # 设置 kf_home
        if not kf_home.endswith('runtime'):
            kf_home = os.path.join(kf_home, 'runtime')

        # 创建独立的 location
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

        # 处理分配的文件
        parse_time_ns = 0
        write_time_ns = 0
        total_rows = 0
        current_time = time.time_ns()

        for csv_file in csv_files:
            # 解析文件
            parse_start = time.time_ns()
            df = pd.read_csv(csv_file)
            quotes = []
            for _, row in df.iterrows():
                quotes.append(csv_to_quote(row))
            parse_end = time.time_ns()
            parse_time_ns += (parse_end - parse_start)

            # 写入文件
            write_start = time.time_ns()
            for quote in quotes:
                writer.write(current_time, quote)
                total_rows += 1
            write_end = time.time_ns()
            write_time_ns += (write_end - write_start)

        # 计算时间
        parse_time_s = parse_time_ns / 1e9
        write_time_s = write_time_ns / 1e9
        total_time_s = parse_time_s + write_time_s
        avg_latency_us = write_time_ns / total_rows / 1000 if total_rows > 0 else 0
        throughput_ops = total_rows / total_time_s if total_time_s > 0 else 0

        result_queue.put({
            'worker_id': worker_id,
            'total_time': total_time_s,
            'parse_time': parse_time_s,
            'write_time': write_time_s,
            'total_rows': total_rows,
            'avg_latency_us': avg_latency_us,
            'throughput_ops': throughput_ops,
            'file_count': len(csv_files)
        })

    except Exception as e:
        result_queue.put({'worker_id': worker_id, 'error': str(e)})


class ParallelWriteTest(BasePerformanceTest):
    """并行写入测试：多个进程同时处理，每个进程处理1个文件"""

    def __init__(self, kf_home=None):
        super().__init__('parallel_write', kf_home)

    def run_test(self, csv_files, parallel_count=5):
        """运行并行写入测试"""
        file_count = len(csv_files)

        print(f"\n{'='*60}")
        print(f"=== 并行写入测试 ===")
        print(f"CSV文件数: {file_count}, 并行进程数: {parallel_count}")
        print(f"每个进程同时处理1个文件")
        print(f"{'='*60}")

        # 分配文件给各个进程
        files_per_worker = file_count // parallel_count
        worker_files = []

        for i in range(parallel_count):
            start_idx = i * files_per_worker
            if i == parallel_count - 1:
                end_idx = file_count
            else:
                end_idx = start_idx + files_per_worker
            worker_files.append(csv_files[start_idx:end_idx])

        # 使用原始 kf_home
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
                target=parallel_worker_process,
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
        total_rows_all = sum(r.get('total_rows', 0) for r in success_results)
        total_parse_time = sum(r.get('parse_time', 0) for r in success_results)
        total_write_time = sum(r.get('write_time', 0) for r in success_results)
        max_time = max(r.get('total_time', 0) for r in success_results)
        total_ops = sum(r.get('throughput_ops', 0) for r in success_results)
        avg_latency = sum(r.get('avg_latency_us', 0) for r in success_results) / len(success_results)

        self.results.update({
            'data_count': file_count,
            'batch_size': 1,
            'parallel_count': parallel_count,
            'total_time': max_time,
            'parse_time': total_parse_time,
            'write_time': total_write_time,
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
        print(f"  CSV解析时间: {total_parse_time:.2f}秒 ({total_parse_time/max_time*100:.1f}%)")
        print(f"  数据库写入时间: {total_write_time:.2f}秒 ({total_write_time/max_time*100:.1f}%)")
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
    # (场景名称, CSV文件数, 批次大小/并行数, 测试类型)

    # === 顺序写入（每次1个文件）===
    ('S1_顺序_10文件', 10, 1, 'sequential'),
    ('S2_顺序_1000文件', 1000, 1, 'sequential'),
    ('S3_顺序_3000文件', 3000, 1, 'sequential'),
    ('S4_顺序_5000文件', 5000, 1, 'sequential'),

    # === 批量写入（每次N个文件）===
    ('B10_批量10_1000文件', 1000, 10, 'batch'),
    ('B100_批量100_1000文件', 1000, 100, 'batch'),
    ('B10_批量10_3000文件', 3000, 10, 'batch'),
    ('B100_批量100_3000文件', 3000, 100, 'batch'),
    ('B10_批量10_5000文件', 5000, 10, 'batch'),
    ('B100_批量100_5000文件', 5000, 100, 'batch'),

    # === 并行写入（N个进程，每个1个文件）===
    ('P5_并行5_1000文件', 1000, 5, 'parallel'),
    ('P10_并行10_1000文件', 1000, 10, 'parallel'),
    ('P5_并行5_3000文件', 3000, 5, 'parallel'),
    ('P10_并行10_3000文件', 3000, 10, 'parallel'),
    ('P5_并行5_5000文件', 5000, 5, 'parallel'),
    ('P10_并行10_5000文件', 5000, 10, 'parallel'),
]


# ============================================================================
# 主入口
# ============================================================================

def main():
    """主入口"""
    import argparse

    parser = argparse.ArgumentParser(description='易筋经性能测试 V2')
    parser.add_argument('--scenario', type=int, default=0,
                        help='场景索引 (0-15)')
    parser.add_argument('--kf-home', type=str, default='/Users/shandian/kungfu',
                        help='KF_HOME 路径')

    args = parser.parse_args()

    if args.scenario >= len(TEST_SCENARIOS):
        print(f"错误: 场景索引 {args.scenario} 不存在，最大为 {len(TEST_SCENARIOS) - 1}")
        return

    scenario_name, file_count, batch_size, mode = TEST_SCENARIOS[args.scenario]
    print(f"\n将运行场景 {args.scenario}: {scenario_name}")
    print(f"  文件数: {file_count}")
    if mode == 'sequential':
        print(f"  模式: 顺序写入 (每次1个文件)")
    elif mode == 'batch':
        print(f"  模式: 批量写入 (每次{batch_size}个文件)")
    else:
        print(f"  模式: 并行写入 ({batch_size}个进程)")

    # 准备数据
    trade_data_dir = os.path.join(args.kf_home, 'TRADE')
    if not os.path.exists(trade_data_dir):
        print(f"错误: 交易数据目录不存在: {trade_data_dir}")
        return

    selector = TradeDataSelector(trade_data_dir)
    selected_files = selector.select_sequential_files(file_count)

    # 运行测试
    if mode == 'sequential':
        test = SequentialWriteTest(args.kf_home)
        result = test.run_test(selected_files)
    elif mode == 'batch':
        test = BatchWriteTest(args.kf_home)
        result = test.run_test(selected_files, batch_size)
    else:  # parallel
        test = ParallelWriteTest(args.kf_home)
        result = test.run_test(selected_files, batch_size)

    if result:
        result['scenario_name'] = scenario_name
        test.save_results()
        print(f"\n场景 '{scenario_name}' 完成！")


if __name__ == '__main__':
    main()
