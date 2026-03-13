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
        self.kf_home = kf_home
        self.monitor = None  # 简化版移除监控
        self.apprentice = None

    def setup_location(self):
        """设置测试使用的 location"""
        locator = yjj.locator(self.kf_home)
        # 使用唯一的 location 标识，避免与 master (system/master/master) 冲突
        location = yjj.location(
            lf.enums.mode.LIVE,
            lf.enums.category.STRATEGY,
            'perf_test',
            'app',
            locator
        )
        return location, locator

    def run_test(self, csv_files, batch_size=1):
        """运行顺序写入测试"""
        print("跳过 master 启动，使用已运行的实例")

        # 1. 设置环境
        location, locator = self.setup_location()

        # 2. 创建 apprentice (强制开启低延迟模式以适配 macOS IPC)
        self.apprentice = yjj.apprentice(location, low_latency=True)

        # 3. 初始化 (连接到 Master 的 Socket)
        print("初始化 apprentice...")
        try:
            self.apprentice.setup()
            print("Apprentice 注册成功!")
        except Exception as e:
            print(f"CRITICAL: Apprentice 初始化失败: {e}")
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