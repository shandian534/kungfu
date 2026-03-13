#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
"""
易筋经时间序列数据库性能测试脚本
"""

import os
import sys
import time
import psutil
import threading
import random
import glob
import pandas as pd
from datetime import datetime

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


class SequentialWriteTest:
    """顺序写入测试"""

    def __init__(self, kf_home=None):
        # 优先使用环境变量 KF_HOME，否则使用默认路径
        if kf_home is None:
            kf_home = os.getenv('KF_HOME', '/Users/shandian/kungfu')
        # 确保路径包含 runtime 子目录，因为 master 使用 runtime 路径
        if not kf_home.endswith('runtime'):
            kf_home = os.path.join(kf_home, 'runtime')
        self.kf_home = kf_home
        self.monitor = None  # 简化版移除监控
        self.apprentice = None

    def setup_location(self):
        """设置测试使用的 location"""
        locator = yjj.locator(self.kf_home)
        print(f"[DEBUG] KF_HOME: {self.kf_home}")

        # master location (检查 master socket 路径)
        master_location = yjj.location(
            lf.enums.mode.LIVE,
            lf.enums.category.SYSTEM,
            'master',
            'master',
            locator
        )
        print(f"[DEBUG] Master location: {master_location.uname}")
        master_pub_path = locator.layout_file(master_location, lf.enums.layout.NANOMSG, 'pub')
        print(f"[DEBUG] Master pub.nn path: {master_pub_path}")

        # 使用唯一的 location 标识，避免与 master (system/master/master) 冲突
        location = yjj.location(
            lf.enums.mode.LIVE,
            lf.enums.category.STRATEGY,
            'perf_test',
            'app',
            locator
        )
        print(f"[DEBUG] Apprentice location: {location.uname}")
        return location, locator

    def run_test(self, csv_files, batch_size=1):
        """运行顺序写入测试"""
        print("跳过 master 启动，使用已运行的实例")

        # 1. 设置环境
        location, locator = self.setup_location()

        # 检查 master socket 是否存在
        import os
        master_nn_path = locator.layout_file(
            yjj.location(lf.enums.mode.LIVE, lf.enums.category.SYSTEM, 'master', 'master', locator),
            lf.enums.layout.NANOMSG,
            'pub'
        )
        master_socket_dir = os.path.dirname(master_nn_path)
        print(f"[DEBUG] Master socket directory: {master_socket_dir}")
        print(f"[DEBUG] Master socket exists: {os.path.exists(master_nn_path)}")
        if os.path.exists(master_socket_dir):
            print(f"[DEBUG] Socket files in directory: {os.listdir(master_socket_dir)}")

        # 2. 创建 apprentice (强制开启低延迟模式以适配 macOS IPC)
        print(f"[DEBUG] Creating apprentice with low_latency=True")
        self.apprentice = yjj.apprentice(location, low_latency=True)

        # 3. 初始化 (连接到 Master 的 Socket)
        print("初始化 apprentice...")
        print(f"[DEBUG] Starting apprentice.setup() - this will try to connect to master and register...")
        try:
            self.apprentice.setup()
            print("Apprentice 注册成功!")
        except Exception as e:
            print(f"CRITICAL: Apprentice 初始化失败: {e}")
            import traceback
            traceback.print_exc()
            raise

        # 4. 获取 writer
        writer = self.apprentice.io_device.open_writer(0)

        # 5. 执行写入
        start_time = time.time_ns()
        for csv_file in csv_files:
            df = pd.read_csv(csv_file)
            for _, row in df.iterrows():
                # 简单的 Quote 构造
                quote = lf.types.Quote()
                quote.data_time = int(row['TIME']) * 1000000
                quote.instrument_id = str(row['SYMBOL'])
                quote.last_price = float(row['PRICE'])
                writer.write(time.time_ns(), quote)

        end_time = time.time_ns()
        print(f"写入完成，耗时: {(end_time - start_time) / 1e9:.2f}秒")


def main():
    kf_home = '/Users/shandian/kungfu'
    trade_data_dir = '/Users/shandian/kungfu/TRADE'

    # 随机选择文件
    all_files = glob.glob(os.path.join(trade_data_dir, '*.csv'))
    csv_files = random.sample(all_files, min(10, len(all_files)))

    test = SequentialWriteTest(kf_home)
    test.run_test(csv_files)


if __name__ == '__main__':
    main()