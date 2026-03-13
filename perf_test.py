#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
易筋经时间序列数据库性能测试脚本
用于测试功夫核心库的写入性能
"""

import os
import sys
import time
import psutil
import threading
import multiprocessing
import random
import glob
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # 使用非GUI后端
import matplotlib.pyplot as plt
from datetime import datetime

# 添加功夫核心库路径
kungfu_core_path = '/Users/shandian/out/kungfu/framework/core/dist/kfc'
sys.path.insert(0, kungfu_core_path)

try:
    from kungfu.__binding__ import longfist as lf
    from kungfu.__binding__ import yijinjing as yjj
except ImportError as e:
    print(f"错误：无法导入功夫核心库: {e}")
    print(f"请确保功夫核心库已正确构建，路径为: {kungfu_core_path}")
    sys.exit(1)


class ResourceMonitor:
    """资源监控器"""

    def __init__(self, interval=0.1):
        self.interval = interval
        self.running = False
        self.data = {'time': [], 'cpu': [], 'memory': []}
        self.process = psutil.Process()
        self.thread = None

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
            current_time = time.time() - self.start_time
            cpu_percent = self.process.cpu_percent()
            memory_percent = self.process.memory_percent()

            self.data['time'].append(current_time)
            self.data['cpu'].append(cpu_percent)
            self.data['memory'].append(memory_percent)

            time.sleep(self.interval)

    def stop(self):
        """停止监控"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)

    def get_data(self):
        """获取监控数据"""
        return pd.DataFrame(self.data)


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


def trade_csv_to_quote(csv_row):
    """将交易数据CSV行转换为Quote对象"""
    quote = lf.types.Quote()

    # 解析日期和时间
    date_str = csv_row['DATE']
    time_val = int(csv_row['TIME'])

    # 转换为纳秒时间戳
    quote.data_time = time_val * 1000000

    # 设置股票代码
    quote.instrument_id = str(int(csv_row['SYMBOL']))  # 确保是字符串
    quote.exchange_id = lf.enums.Exchange.SSE

    # 设置价格和数量
    quote.last_price = float(csv_row['PRICE'])
    quote.volume = int(csv_row['SIZE'])

    # 设置其他必要字段
    quote.open_interest = 0
    quote.bid_price1 = quote.last_price - 0.01
    quote.ask_price1 = quote.last_price + 0.01
    quote.bid_volume1 = 100
    quote.ask_volume1 = 100

    return quote


class SequentialWriteTest:
    """顺序写入测试"""

    def __init__(self, kf_home=None):
        self.test_name = 'sequential_write'
        self.kf_home = kf_home or os.path.expanduser('~/kungfu_perf_test')
        self.monitor = ResourceMonitor()

        # 测试结果
        self.results = {
            'test_name': self.test_name,
            'timestamp': datetime.now().isoformat(),
            'data_count': 0,
            'batch_size': 0,
            'total_time': 0,
            'avg_latency_us': 0,
            'throughput_ops': 0,
            'resource_data': None
        }

    def setup_location(self):
        """设置测试使用的 location"""
        locator = yjj.locator(self.kf_home, 'live', lf.enums.category.MD)
        location = yjj.location(
            lf.enums.mode.LIVE,
            lf.enums.category.MD,
            'test',
            'perf_test',
            locator
        )
        return location, locator

    def measure_write_from_csv(self, writer, csv_files, batch_size=1):
        """从CSV文件读取并测量写入性能"""
        start_time = time.time_ns()
        total_rows = 0

        if batch_size == 1:
            # 顺序处理每个CSV文件
            for csv_file in csv_files:
                try:
                    df = pd.read_csv(csv_file)
                    for _, row in df.iterrows():
                        quote = trade_csv_to_quote(row)
                        writer.write(time.time_ns(), quote)
                        total_rows += 1
                except Exception as e:
                    print(f"处理文件 {csv_file} 时出错: {e}")
                    continue
        else:
            # 批量处理CSV文件
            for i in range(0, len(csv_files), batch_size):
                batch_files = csv_files[i:i+batch_size]
                for csv_file in batch_files:
                    try:
                        df = pd.read_csv(csv_file)
                        for _, row in df.iterrows():
                            quote = trade_csv_to_quote(row)
                            writer.write(time.time_ns(), quote)
                            total_rows += 1
                    except Exception as e:
                        print(f"处理文件 {csv_file} 时出错: {e}")
                        continue

        end_time = time.time_ns()

        # 计算指标
        total_time_s = (end_time - start_time) / 1e9
        avg_latency_us = (end_time - start_time) / total_rows / 1000 if total_rows > 0 else 0
        throughput_ops = total_rows / total_time_s if total_time_s > 0 else 0

        return {
            'total_time': total_time_s,
            'total_rows': total_rows,
            'avg_latency_us': avg_latency_us,
            'throughput_ops': throughput_ops
        }

    def run_test(self, csv_files, batch_size=1):
        """运行顺序写入测试"""
        file_count = len(csv_files)

        print(f"\n=== 顺序写入测试 ===")
        print(f"CSV文件数: {file_count}, 批次大小: {batch_size}")

        # 设置环境
        location, locator = self.setup_location()
        writer = yjj.writer(location, 0, False)

        # 开始监控
        self.monitor.start()

        # 执行写入
        perf_metrics = self.measure_write_from_csv(writer, csv_files, batch_size)

        # 停止监控
        self.monitor.stop()

        # 记录结果
        self.results.update({
            'data_count': file_count,
            'batch_size': batch_size,
            **perf_metrics,
            'resource_data': self.monitor.get_data()
        })

        # 打印结果
        print(f"总耗时: {perf_metrics['total_time']:.2f}秒")
        print(f"处理行数: {perf_metrics['total_rows']}")
        print(f"吞吐量: {perf_metrics['throughput_ops']:.0f} ops")
        print(f"平均延迟: {perf_metrics['avg_latency_us']:.2f}微秒")

        return self.results

    def save_results(self):
        """保存测试结果"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_dir = os.path.join(self.kf_home, 'test_results')
        os.makedirs(result_dir, exist_ok=True)

        result_file = os.path.join(
            result_dir,
            f'{self.test_name}_{timestamp}.json'
        )

        import json
        with open(result_file, 'w') as f:
            results = self.results.copy()
            if results['resource_data'] is not None:
                results['resource_data'] = results['resource_data'].to_dict('records')
            json.dump(results, f, indent=2)

        print(f"结果已保存到: {result_file}")
        return result_file


class PerformanceReporter:
    """性能测试报告生成器"""

    def __init__(self, output_dir):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def plot_resource_usage(self, test_result, save_path=None):
        """绘制资源使用情况"""
        resource_data = test_result['resource_data']

        if resource_data is None or resource_data.empty:
            print("无资源监控数据")
            return

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

        # CPU使用率曲线
        ax1.plot(resource_data['time'], resource_data['cpu'], 'r-', label='usage of CPU(%)')
        ax1.set_ylabel('usage of CPU (%)')
        ax1.grid(True)
        ax1.legend()

        # 内存使用率曲线
        ax2.plot(resource_data['time'], resource_data['memory'], 'b-', label='usage of memory(%)')
        ax2.set_xlabel('time (s)')
        ax2.set_ylabel('usage of memory (%)')
        ax2.grid(True)
        ax2.legend()

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"图表已保存: {save_path}")

        plt.close()

    def generate_report(self, test_result):
        """生成测试报告"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # 生成资源使用图
        save_path = os.path.join(
            self.output_dir,
            f'{test_result["test_name"]}_resource_{timestamp}.png'
        )
        self.plot_resource_usage(test_result, save_path)

        print(f"\n测试报告已生成到: {self.output_dir}")


def quick_test():
    """快速测试 - 验证环境"""
    print("=" * 60)
    print("易筋经性能测试 - 快速验证")
    print("=" * 60)

    kf_home = os.path.expanduser('~/kungfu_perf_test')
    trade_data_dir = '/Users/shandian/kungfu/TRADE'
    output_dir = os.path.join(kf_home, 'reports')

    # 创建测试目录
    os.makedirs(kf_home, exist_ok=True)

    # 使用真实交易数据
    selector = TradeDataSelector(trade_data_dir)

    # 随机选择少量文件进行快速测试
    csv_files = selector.select_random_files(10)

    print("\n选择的文件（前3个）：")
    for f in csv_files[:3]:
        print(f"  {os.path.basename(f)}")

    # 运行测试
    test = SequentialWriteTest(kf_home)
    result = test.run_test(csv_files, batch_size=1)

    # 保存结果
    test.save_results()

    # 生成报告
    reporter = PerformanceReporter(output_dir)
    reporter.generate_report(result)

    print("\n" + "=" * 60)
    print("快速测试完成！")
    print("=" * 60)


def run_single_test(file_count, batch_size=1):
    """运行单个测试场景"""
    print("=" * 60)
    print(f"易筋经性能测试 - {file_count} 个文件")
    print("=" * 60)

    kf_home = os.path.expanduser('~/kungfu_perf_test')
    trade_data_dir = '/Users/shandian/kungfu/TRADE'
    output_dir = os.path.join(kf_home, 'reports')

    # 创建测试目录
    os.makedirs(kf_home, exist_ok=True)

    # 使用真实交易数据
    selector = TradeDataSelector(trade_data_dir)
    csv_files = selector.select_random_files(file_count)

    # 运行测试
    test = SequentialWriteTest(kf_home)
    result = test.run_test(csv_files, batch_size=batch_size)

    # 保存结果
    test.save_results()

    # 生成报告
    reporter = PerformanceReporter(output_dir)
    reporter.generate_report(result)

    return result


def main():
    """主函数"""
    if len(sys.argv) > 1:
        if sys.argv[1] == 'quick':
            # 快速测试
            quick_test()
        elif sys.argv[1] == 'test':
            # 指定文件数的测试
            file_count = int(sys.argv[2]) if len(sys.argv) > 2 else 100
            batch_size = int(sys.argv[3]) if len(sys.argv) > 3 else 1
            run_single_test(file_count, batch_size)
        else:
            print("用法:")
            print("  python perf_test.py quick          # 快速验证测试")
            print("  python perf_test.py test 100      # 测试100个文件")
            print("  python perf_test.py test 1000 10  # 测试1000个文件，批次大小10")
    else:
        # 默认运行快速测试
        quick_test()


if __name__ == '__main__':
    main()
