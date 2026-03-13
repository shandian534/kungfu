# 易筋经时间序列数据库性能测试方案

## 1. 测试目标

测试易筋经（yijinjing）时间序列数据库在不同写入场景下的性能表现，包括：

- **写入延迟**：单个数据写入的平均时间
- **吞吐量**：单位时间内写入的数据量
- **资源占用**：CPU和内存使用情况
- **扩展性**：不同数据规模和并行度下的性能表现

## 2. 测试环境

### 2.1 硬件环境

```
CPU: [待填写]
内存: [待填写]
磁盘: SSD [待填写]
操作系统: macOS/Linux [待填写]
```

### 2.2 软件环境

```bash
功夫版本: 2.4.77
Python版本: 3.9
测试框架: 自定义 + psutil + matplotlib
```

### 2.3 环境准备

```bash
# 安装依赖
pip install psutil matplotlib pandas numpy

# 设置环境变量
export KF_HOME=~/kungfu_perf_test
export KF_LOG_LEVEL=info  # 减少日志对性能的影响
```

## 3. 测试场景设计

### 3.1 测试维度

| 维度 | 参数值 | 说明 |
|------|--------|------|
| **数据规模** | 10, 1000, 3000, 5000 | CSV文件数量 |
| **批次大小** | 10, 100 | 每批次处理的CSV文件数 |
| **并行数** | 5, 10 | 同时处理的进程/线程数 |
| **写入模式** | 顺序、批量、并行 | 三种处理方式 |

### 3.2 测试场景矩阵

| 场景 | 数据规模 | 批次大小 | 并行数 | 写入模式 |
|------|----------|----------|--------|----------|
| S1 | 10 | - | 1 | 顺序写入 |
| S2 | 1000 | - | 1 | 顺序写入 |
| S3 | 1000 | 10 | 1 | 批量写入 |
| S4 | 1000 | 100 | 1 | 批量写入 |
| S5 | 1000 | - | 5 | 并行写入 |
| S6 | 1000 | - | 10 | 并行写入 |
| S7 | 3000 | 100 | 5 | 并行批量写入 |
| S8 | 5000 | 100 | 10 | 并行批量写入 |

## 4. 测试数据设计

### 4.1 数据结构

使用功夫的 longfist 数据类型，以 `Quote` (行情数据) 为例：

```python
from kungfu.__binding__ import longfist as lf

# 行情数据结构
quote = lf.types.Quote()
quote.data_time = current_time_in_nano()
quote.instrument_id = "600000"
quote.exchange_id = lf.enums.Exchange.SSE
quote.last_price = 10.5
# ... 其他字段
```

### 4.2 数据生成

```python
import time
import random

def generate_quotes(count):
    """生成指定数量的测试行情数据"""
    quotes = []
    base_time = time.time_ns()

    for i in range(count):
        quote = lf.types.Quote()
        quote.data_time = base_time + i * 1000000  # 1ms间隔
        quote.instrument_id = f"INSTR_{i % 100:06d}"
        quote.exchange_id = lf.enums.Exchange.SSE
        quote.last_price = random.uniform(10.0, 100.0)
        quote.volume = random.randint(100, 10000)
        # 设置其他必要字段...
        quotes.append(quote)

    return quotes
```

## 5. 测试代码框架

### 5.1 基础测试类

```python
import os
import time
import psutil
import threading
import multiprocessing
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

from kungfu.__binding__ import longfist as lf
from kungfu.__binding__ import yijinjing as yjj
from kungfu.yijinjing import journal as kfj

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
        self.thread.start()

    def _monitor(self):
        """监控线程"""
        while self.running:
            current_time = time.time() - self.start_time
            cpu_percent = self.process.cpu_percent()
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()

            self.data['time'].append(current_time)
            self.data['cpu'].append(cpu_percent)
            self.data['memory'].append(memory_percent)

            time.sleep(self.interval)

    def stop(self):
        """停止监控"""
        self.running = False
        if self.thread:
            self.thread.join()

    def get_data(self):
        """获取监控数据"""
        return pd.DataFrame(self.data)


class YijinjingPerformanceTest:
    """易筋经性能测试基类"""

    def __init__(self, test_name, kf_home=None):
        self.test_name = test_name
        self.kf_home = kf_home or os.getenv('KF_HOME', '~/kungfu_perf_test')
        self.runtime_dir = os.path.join(self.kf_home, 'runtime')
        self.monitor = ResourceMonitor()

        # 测试结果
        self.results = {
            'test_name': test_name,
            'timestamp': datetime.now().isoformat(),
            'data_count': 0,
            'batch_size': 0,
            'parallel_count': 0,
            'total_time': 0,
            'avg_latency_us': 0,
            'throughput_ops': 0,
            'resource_data': None
        }

    def setup_location(self, category='md', group='test', name='perf_test'):
        """设置测试使用的 location"""
        locator = yjj.locator(self.kf_home, 'live', lf.enums.category.MD)
        location = yjj.location(
            lf.enums.mode.LIVE,
            lf.enums.category.MD,
            group,
            name,
            locator
        )
        return location, locator

    def create_writer(self, location):
        """创建 writer"""
        writer = yjj.writer(location, 0, False)
        return writer

    def run_test(self, data_count, batch_size=1, parallel_count=1):
        """运行测试（子类实现）"""
        raise NotImplementedError

    def measure_write(self, writer, quotes, batch_size=1):
        """测量写入性能"""
        start_time = time.time_ns()

        if batch_size == 1:
            # 顺序写入
            for quote in quotes:
                writer.write(time.time_ns(), quote)
        else:
            # 批量写入
            for i in range(0, len(quotes), batch_size):
                batch = quotes[i:i+batch_size]
                for quote in batch:
                    writer.write(time.time_ns(), quote)

        end_time = time.time_ns()

        # 计算指标
        total_time_s = (end_time - start_time) / 1e9
        avg_latency_us = (end_time - start_time) / len(quotes) / 1000
        throughput_ops = len(quotes) / total_time_s

        return {
            'total_time': total_time_s,
            'avg_latency_us': avg_latency_us,
            'throughput_ops': throughput_ops
        }

    def save_results(self):
        """保存测试结果"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_file = os.path.join(
            self.kf_home, 'test_results',
            f'{self.test_name}_{timestamp}.json'
        )

        os.makedirs(os.path.dirname(result_file), exist_ok=True)

        import json
        with open(result_file, 'w') as f:
            # 转换 resource_data 为可序列化格式
            results = self.results.copy()
            if results['resource_data'] is not None:
                results['resource_data'] = results['resource_data'].to_dict('records')
            json.dump(results, f, indent=2)

        print(f"结果已保存到: {result_file}")
        return result_file
```

### 5.2 顺序写入测试

```python
class SequentialWriteTest(YijinjingPerformanceTest):
    """顺序写入测试"""

    def __init__(self, kf_home=None):
        super().__init__('sequential_write', kf_home)

    def run_test(self, data_count, batch_size=1, parallel_count=1):
        """运行顺序写入测试"""
        print(f"\n=== 顺序写入测试 ===")
        print(f"数据量: {data_count}, 批次大小: {batch_size}")

        # 设置环境
        location, locator = self.setup_location()
        writer = self.create_writer(location)

        # 生成测试数据
        quotes = generate_quotes(data_count)
        print(f"生成 {len(quotes)} 条测试数据")

        # 开始监控
        self.monitor.start()

        # 执行写入
        perf_metrics = self.measure_write(writer, quotes, batch_size)

        # 停止监控
        self.monitor.stop()

        # 记录结果
        self.results.update({
            'data_count': data_count,
            'batch_size': batch_size,
            'parallel_count': 1,
            **perf_metrics,
            'resource_data': self.monitor.get_data()
        })

        # 打印结果
        print(f"总耗时: {perf_metrics['total_time']:.2f}秒")
        print(f"平均延迟: {perf_metrics['avg_latency_us']:.2f}微秒")
        print(f"吞吐量: {perf_metrics['throughput_ops']:.0f} ops")

        return self.results
```

### 5.3 并行写入测试

```python
class ParallelWriteTest(YijinjingPerformanceTest):
    """并行写入测试"""

    def __init__(self, kf_home=None):
        super().__init__('parallel_write', kf_home)

    def worker_process(self, worker_id, data_count, batch_size, result_queue):
        """工作进程"""
        try:
            # 每个进程创建独立的 location
            location, locator = self.setup_location(
                group='test',
                name=f'perf_test_worker_{worker_id}'
            )
            writer = self.create_writer(location)

            # 生成数据
            quotes = generate_quotes(data_count)

            # 执行写入并测量
            start_time = time.time_ns()

            if batch_size == 1:
                for quote in quotes:
                    writer.write(time.time_ns(), quote)
            else:
                for i in range(0, len(quotes), batch_size):
                    batch = quotes[i:i+batch_size]
                    for quote in batch:
                        writer.write(time.time_ns(), quote)

            end_time = time.time_ns()

            total_time_s = (end_time - start_time) / 1e9
            avg_latency_us = (end_time - start_time) / len(quotes) / 1000
            throughput_ops = len(quotes) / total_time_s

            result_queue.put({
                'worker_id': worker_id,
                'total_time': total_time_s,
                'avg_latency_us': avg_latency_us,
                'throughput_ops': throughput_ops
            })

        except Exception as e:
            result_queue.put({'worker_id': worker_id, 'error': str(e)})

    def run_test(self, data_count, batch_size=1, parallel_count=5):
        """运行并行写入测试"""
        print(f"\n=== 并行写入测试 ===")
        print(f"数据量: {data_count}, 批次大小: {batch_size}, 并行数: {parallel_count}")

        # 开始监控
        self.monitor.start()

        # 创建进程池
        result_queue = multiprocessing.Queue()
        processes = []

        for i in range(parallel_count):
            p = multiprocessing.Process(
                target=self.worker_process,
                args=(i, data_count, batch_size, result_queue)
            )
            processes.append(p)
            p.start()

        # 等待所有进程完成
        for p in processes:
            p.join()

        # 停止监控
        self.monitor.stop()

        # 收集结果
        results = []
        while not result_queue.empty():
            results.append(result_queue.get())

        # 计算总体指标
        total_ops = sum(r.get('throughput_ops', 0) for r in results)
        total_data_count = sum(r.get('data_count', data_count) for r in results)

        self.results.update({
            'data_count': total_data_count,
            'batch_size': batch_size,
            'parallel_count': parallel_count,
            'total_time': max(r.get('total_time', 0) for r in results),
            'avg_latency_us': sum(r.get('avg_latency_us', 0) for r in results) / len(results),
            'throughput_ops': total_ops,
            'resource_data': self.monitor.get_data(),
            'worker_results': results
        })

        # 打印结果
        print(f"总数据量: {total_data_count}")
        print(f"总吞吐量: {total_ops:.0f} ops")
        print(f"平均延迟: {self.results['avg_latency_us']:.2f}微秒")

        return self.results
```

## 6. 性能指标与图表

### 6.1 性能指标

| 指标 | 说明 | 计算方法 |
|------|------|----------|
| **写入延迟** | 单条数据写入的平均时间 | 总耗时 / 数据条数 |
| **吞吐量** | 每秒写入的数据条数 | 数据条数 / 总耗时 |
| **CPU使用率** | 测试期间CPU占用百分比 | psutil监控 |
| **内存使用率** | 测试期间内存占用百分比 | psutil监控 |
| **扩展系数** | 并行效率 | 并行吞吐量 / 串行吞吐量 |

### 6.2 图表绘制

```python
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
        ax1.plot(resource_data['time'], resource_data['cpu'], 'r-', label='CPU使用率 (%)')
        ax1.set_ylabel('CPU使用率 (%)')
        ax1.set_title(f"{test_result['test_name']} - 资源使用情况")
        ax1.grid(True)
        ax1.legend()

        # 内存使用率曲线
        ax2.plot(resource_data['time'], resource_data['memory'], 'b-', label='内存使用率 (%)')
        ax2.set_xlabel('时间 (秒)')
        ax2.set_ylabel('内存使用率 (%)')
        ax2.grid(True)
        ax2.legend()

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"图表已保存: {save_path}")

        plt.close()

    def plot_performance_comparison(self, results, save_path=None):
        """绘制性能对比图"""
        # 提取数据
        test_names = [r['test_name'] for r in results]
        throughputs = [r['throughput_ops'] for r in results]
        latencies = [r['avg_latency_us'] for r in results]

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

        # 吞吐量对比
        x = np.arange(len(test_names))
        width = 0.35

        ax1.bar(x, throughputs, width, label='吞吐量 (ops)', color='steelblue')
        ax1.set_ylabel('吞吐量 (ops)')
        ax1.set_title('不同场景下的吞吐量对比')
        ax1.set_xticks(x)
        ax1.set_xticklabels(test_names, rotation=45, ha='right')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # 延迟对比
        ax2.bar(x, latencies, width, label='平均延迟 (μs)', color='coral')
        ax2.set_ylabel('平均延迟 (微秒)')
        ax2.set_title('不同场景下的写入延迟对比')
        ax2.set_xticks(x)
        ax2.set_xticklabels(test_names, rotation=45, ha='right')
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"对比图已保存: {save_path}")

        plt.close()

    def plot_scalability(self, results, save_path=None):
        """绘制扩展性图表"""
        # 按并行数分组
        parallel_1 = [r for r in results if r['parallel_count'] == 1]
        parallel_5 = [r for r in results if r['parallel_count'] == 5]
        parallel_10 = [r for r in results if r['parallel_count'] == 10]

        data_counts = sorted(set(r['data_count'] for r in results))

        fig, ax = plt.subplots(figsize=(10, 6))

        for parallel_count, color, label in [(1, 'blue', '串行'), (5, 'green', '5并行'), (10, 'red', '10并行')]:
            data = [r for r in results if r['parallel_count'] == parallel_count]
            if data:
                x = [r['data_count'] for r in data]
                y = [r['throughput_ops'] for r in data]
                ax.plot(x, y, marker='o', label=label, color=color, linewidth=2)

        ax.set_xlabel('数据规模 (条)')
        ax.set_ylabel('吞吐量 (ops)')
        ax.set_title('不同并行数下的扩展性')
        ax.legend()
        ax.grid(True, alpha=0.3)

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"扩展性图已保存: {save_path}")

        plt.close()

    def generate_report(self, all_results):
        """生成完整测试报告"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # 生成各测试的资源使用图
        for result in all_results:
            test_name = result['test_name']
            save_path = os.path.join(
                self.output_dir,
                f'{test_name}_resource_{timestamp}.png'
            )
            self.plot_resource_usage(result, save_path)

        # 生成性能对比图
        comparison_path = os.path.join(
            self.output_dir,
            f'performance_comparison_{timestamp}.png'
        )
        self.plot_performance_comparison(all_results, comparison_path)

        # 生成扩展性图
        scalability_path = os.path.join(
            self.output_dir,
            f'scalability_{timestamp}.png'
        )
        self.plot_scalability(all_results, scalability_path)

        # 生成汇总表格
        summary_path = os.path.join(
            self.output_dir,
            f'test_summary_{timestamp}.csv'
        )
        self._generate_summary_table(all_results, summary_path)

        print(f"\n测试报告已生成到: {self.output_dir}")

    def _generate_summary_table(self, results, output_path):
        """生成汇总表格"""
        df_data = []
        for r in results:
            df_data.append({
                '测试名称': r['test_name'],
                '数据量': r['data_count'],
                '批次大小': r['batch_size'],
                '并行数': r['parallel_count'],
                '总耗时(秒)': f"{r['total_time']:.2f}",
                '平均延迟(微秒)': f"{r['avg_latency_us']:.2f}",
                '吞吐量(ops)': f"{r['throughput_ops']:.0f}"
            })

        df = pd.DataFrame(df_data)
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"汇总表格已保存: {output_path}")
```

## 7. 测试执行

### 7.1 完整测试流程

```python
def run_all_tests():
    """运行所有测试场景"""
    print("=" * 60)
    print("易筋经时间序列数据库性能测试")
    print("=" * 60)

    # 设置测试目录
    kf_home = os.path.expanduser('~/kungfu_perf_test')
    output_dir = os.path.join(kf_home, 'reports')

    all_results = []

    # 测试场景配置
    test_scenarios = [
        # (数据量, 批次大小, 并行数, 测试类)
        (10, 1, 1, 'sequential'),
        (1000, 1, 1, 'sequential'),
        (1000, 10, 1, 'sequential'),
        (1000, 100, 1, 'sequential'),
        (1000, 1, 5, 'parallel'),
        (1000, 1, 10, 'parallel'),
        (3000, 100, 5, 'parallel'),
        (5000, 100, 10, 'parallel'),
    ]

    for data_count, batch_size, parallel_count, mode in test_scenarios:
        try:
            if mode == 'sequential':
                test = SequentialWriteTest(kf_home)
            else:
                test = ParallelWriteTest(kf_home)

            result = test.run_test(data_count, batch_size, parallel_count)
            all_results.append(result)

            # 保存单次结果
            test.save_results()

            # 短暂休息，避免资源占用
            time.sleep(2)

        except Exception as e:
            print(f"测试失败: {e}")
            continue

    # 生成报告
    reporter = PerformanceReporter(output_dir)
    reporter.generate_report(all_results)

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)

    return all_results


if __name__ == '__main__':
    # 运行测试
    results = run_all_tests()

    # 打印汇总
    print("\n=== 测试结果汇总 ===")
    for r in results:
        print(f"\n{r['test_name']}:")
        print(f"  数据量: {r['data_count']}, 批次: {r['batch_size']}, 并行: {r['parallel_count']}")
        print(f"  吞吐量: {r['throughput_ops']:.0f} ops")
        print(f"  延迟: {r['avg_latency_us']:.2f} μs")
```

### 7.2 快速测试脚本

```python
def quick_test():
    """快速测试 - 验证环境"""
    kf_home = os.path.expanduser('~/kungfu_perf_test')

    test = SequentialWriteTest(kf_home)
    result = test.run_test(data_count=100, batch_size=1)

    print("\n快速测试完成，环境验证成功！")
    return result
```

## 8. 预期输出

### 8.1 控制台输出

```
==========================================================
易筋经时间序列数据库性能测试
==========================================================

=== 顺序写入测试 ===
数据量: 1000, 批次大小: 1
生成 1000 条测试数据
总耗时: 2.45秒
平均延迟: 2450.00微秒
吞吐量: 408 ops

=== 并行写入测试 ===
数据量: 1000, 批次大小: 1, 并行数: 5
总数据量: 5000
总吞吐量: 1850 ops
平均延迟: 2700.00微秒

==========================================================
测试完成!
==========================================================
```

### 8.2 生成的图表

1. **资源使用图**：CPU和内存随时间变化曲线
2. **性能对比图**：不同场景的吞吐量和延迟对比
3. **扩展性图**：不同并行数下的性能扩展情况

### 8.3 数据文件

```
~/kungfu_perf_test/
├── runtime/              # 运行时数据
├── test_results/         # 测试结果JSON
├── reports/              # 测试报告
│   ├── sequential_write_resource_20260313_150000.png
│   ├── parallel_write_resource_20260313_150005.png
│   ├── performance_comparison_20260313_150010.png
│   ├── scalability_20260313_150010.png
│   └── test_summary_20260313_150010.csv
```

## 9. 测试注意事项

### 9.1 环境隔离

```bash
# 每次测试前清理环境
rm -rf ~/kungfu_perf_test/runtime/*

# 或使用独立的测试目录
export KF_HOME=~/kungfu_test_run_$(date +%s)
```

### 9.2 系统资源

- 关闭不必要的后台进程
- 确保有足够的磁盘空间（至少10GB）
- 如果可能，禁用 swap

### 9.3 数据一致性

- 确保每次测试使用相同的数据模式
- 记录测试时的系统负载
- 多次运行取平均值

### 9.4 故障处理

```python
# 测试失败时的清理
def cleanup_on_failure(test_instance):
    """清理失败的测试"""
    try:
        # 停止监控
        test_instance.monitor.stop()

        # 清理 runtime 数据
        import shutil
        if os.path.exists(test_instance.runtime_dir):
            shutil.rmtree(test_instance.runtime_dir)

        print("测试失败，环境已清理")
    except Exception as e:
        print(f"清理失败: {e}")
```

## 10. 后续优化方向

### 10.1 性能优化测试

- 测试不同的 journal page 大小
- 测试低延迟模式（`-x` 参数）的影响
- 测试不同的数据类型

### 10.2 极限测试

- 大数据量测试（100K、1M、10M）
- 长时间稳定性测试（持续写入1小时）
- 故障恢复测试

### 10.3 对比测试

- 与其他时间序列数据库对比（InfluxDB、TimescaleDB）
- 不同硬件配置下的性能对比
- 不同操作系统下的性能对比

## 11. 参考资料

- 功夫核心库文档：https://docs.libkungfu.cc
- Journal 源码：`framework/core/src/include/kungfu/yijinjing/journal/`
- Longfist 数据类型：`framework/core/src/include/kungfu/longfist/`

---

**文档版本**：v1.0
**创建日期**：2026-03-13
**最后更新**：2026-03-13
