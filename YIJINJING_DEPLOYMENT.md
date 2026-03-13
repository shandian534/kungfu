# 易筋经（Yijinjing）性能测试部署指南

本文档提供易筋经组件在本机部署的完整指南，用于进行性能测试。

## 目录

- [系统架构概述](#系统架构概述)
- [环境准备](#环境准备)
- [构建系统](#构建系统)
- [部署步骤](#部署步骤)
- [核心组件说明](#核心组件说明)
- [性能测试](#性能测试)
- [监控和调试](#监控和调试)
- [常见问题](#常见问题)

## 系统架构概述

易筋经是功夫系统的核心组件，提供超低延迟时间序列数据存储和处理能力。

### 主要组件

**journal（日志系统）**
- 纳秒级时间序列内存数据库
- 核心：page、frame、journal 三层数据结构
- 支持实时数据写入和历史数据回放

**practice（实践框架）**
- **master（主控进程）**：系统中央协调器，管理所有进程
- **apprentice（学徒进程）**：执行具体业务逻辑的进程
- **hero（英雄）**：基础事件处理类

**io（I/O层）**
- 负责数据读写操作
- 支持多种数据源和目标

### 架构关系

```
┌─────────────────────────────────────┐
│           Master Process            │
│  (进程管理、注册、交易日期维护)        │
└──────────┬──────────────────────────┘
           │
           ├── Journal (低延迟通信)
           │
    ┌──────┴──────┬──────────┬──────────┐
    │             │          │          │
┌───▼────┐  ┌────▼────┐ ┌───▼────┐ ┌──▼─────┐
│  MD    │  │   TD    │ │Strategy│ │ Ledger │
│(行情)  │  │ (交易)  │ │ (策略)  │ │(账本)  │
└────────┘  └─────────┘ └────────┘ └────────┘
```

## 环境准备

### 系统要求

- **操作系统**：Windows、macOS、Linux
- **编译器**：支持 C++20
- **内存**：建议 8GB 以上
- **磁盘**：SSD 推荐，用于 journal 存储

### 依赖工具

```bash
# Node.js 包管理器
yarn (^1.x)

# Python 环境
Python 3.9
pipenv (>=2023.9.1)

# 构建工具
cmake (>=3.15)
```

### 环境变量

```bash
# KF_HOME - 功夫文件基础目录
# 默认值：~/kungfu
export KF_HOME=~/kungfu

# KF_LOG_LEVEL - 日志级别
# 可选值：trace、debug、info、warn、error
# 默认值：info
export KF_LOG_LEVEL=trace

# KF_NO_EXT - 禁用扩展（纯易筋经测试）
# 设置为任意值即启用
export KF_NO_EXT=1
```

## 构建系统

### 完整构建流程

```bash
# 1. 获取代码（必须使用 git clone）
git clone https://github.com/kungfu-trader/kungfu.git
cd kungfu

# 2. 安装依赖
yarn install --frozen-lockfile

# 3. 构建所有组件
yarn build

# 4. 打包应用
yarn package
```

### 快速重建

```bash
# 清理并重新构建
yarn rebuild

# 仅构建核心库
yarn build:core

# 重新构建核心库
yarn rebuild:core
```

### 构建产物

构建完成后，产物位于：
```
artifact/build/          # 构建输出
artifact/dist/          # 分发文件
```

## 部署步骤

### 步骤 1：配置环境

```bash
# 创建工作目录
mkdir -p ~/kungfu

# 设置环境变量
export KF_HOME=~/kungfu
export KF_LOG_LEVEL=trace
```

### 步骤 2：启动 Master 进程

Master 是整个系统的中央协调器，必须首先启动。

```bash
# 方法 1：使用 kfc 命令（推荐）
yarn workspace @kungfu-trader/kungfu-core kfc run service master

# 方法 2：使用 Python 接口
python -m kungfu run service master

# 方法 3：低延迟模式（性能测试推荐）
kfc run -x service master

# 正确：
 kfc run -c system -g master -n master
```

**Master 启动验证：**
- 查看日志输出，确认 "master started" 消息
- 检查进程：`ps aux | grep master`

### 步骤 3：启动 Apprentice 进程

在新的终端窗口中启动具体的业务进程。

```bash
# 启动策略服务
kfc run -c strategy -g test -n perf examples/strategy-python-simple/simple_trade_sim.py

# 启动账本服务
kfc run service ledger

# 启动行情数据服务（使用模拟数据）
kfc run -c md -g sim -n xtp
```

**参数说明：**
- `-c, --category`：类别（md/td/strategy/system）
- `-g, --group`：组名（sim/xtp/自定义）
- `-n, --name`：实例名称
- `-x, --low-latency`：启用低延迟模式
- `-m, --mode`：运行模式（live/replay/backtest）

### 步骤 4：验证部署

```bash
# 查看所有 session
kfc journal sessions

# 查看特定 session 信息
kfc journal show -i 1

# 查看运行中的进程
kfc ps
```

## 核心组件说明

### Master（主控进程）

**位置：**`framework/core/src/python/kungfu/yijinjing/practice/master.py:34`

**职责：**
- 管理所有 apprentice 进程的生命周期
- 处理进程注册和注销
- 维护交易日期和日历
- 分发配置和佣金信息
- 监控进程健康状态

**关键方法：**
- `on_register()`: 处理新进程注册
- `on_interval_check()`: 定期检查任务
- `publish_trading_day()`: 发布交易日期

### Apprentice（学徒进程）

**位置：**`framework/core/src/python/kungfu/yijinjing/practice/apprentice.py:13`

**职责：**
- 执行具体业务逻辑
- 通过 journal 与 master 通信
- 处理市场数据和订单事件
- 维护本地状态

**生命周期：**
1. 创建并配置 location
2. 向 master 注册
3. 开始处理事件
4. 收到停止信号时优雅退出

### Journal（日志系统）

**核心概念：**

**Page（页）**
- 固定大小的内存映射文件（默认 64MB）
- 循环写入，支持高效读写
- 位置：`$KF_HOME/runtime/{category}/{group}/{name}/journal/{mode}/`

**Frame（帧）**
- 最小数据单元，包含数据和时间戳
- 纳秒级时间精度
- 支持多种数据类型（Quote、Order、Trade 等）

**Journal（日志）**
- 逻辑上的数据流集合
- 由多个 page 组成
- 支持读写分离

**Journal 命令：**

```bash
# 列出所有 session
kfc journal sessions

# 按 duration 排序
kfc journal sessions --sortby duration

# 查看 session 详细数据
kfc journal show -i <session_id> -t all

# 导出为 CSV
kfc journal show -i <session_id> -t all -o output.csv

# 追踪模式（实时显示）
kfc journal trace -i <session_id> -t all

# 清理 journal 文件
kfc journal clean --dry  # 预览
kfc journal clean        # 执行

# 归档
kfc journal archive
```

## 性能测试

### 基础性能测试

```bash
# 1. 启动 master（低延迟模式）
kfc run -x service master &
MASTER_PID=$!

# 2. 运行测试策略
cd examples/strategy-python-simple
kfc run -c strategy -g test -n perf simple_trade_sim.py &
STRATEGY_PID=$!

# 3. 运行指定时间后停止
sleep 300  # 运行 5 分钟

# 4. 清理进程
kill $STRATEGY_PID
kill $MASTER_PID

# 5. 分析性能数据
kfc journal sessions --sortby duration
kfc journal show -i 1 -o perf_test.csv
```

### 延迟测试

测试从数据产生到处理的端到端延迟：

```bash
# 使用 trace 命令实时监控延迟
kfc journal trace -i <session_id> -t all
```

**关注指标：**
- 数据生成时间戳
- 处理时间戳
- 时间差（延迟）

### 吞吐量测试

测试系统处理能力：

```bash
# 运行高频数据生成策略
kfc run -c md -g test -n high_freq examples/strategy-python-simple/simple_trade_sim.py

# 监控处理速度
watch -n 1 'kfc journal sessions | tail -n 5'
```

**关注指标：**
- 每秒处理的 frame 数量
- CPU 使用率
- 内存占用

### 资源使用监控

```bash
# 监控进程资源
top -p $(pgrep -f "kfc run")

# 监控磁盘 I/O
iotop -o

# 监控 journal 文件大小
watch -n 1 'du -sh $KF_HOME/runtime/*'
```

## 监控和调试

### 日志管理

**日志位置：**
```
$KF_HOME/runtime/{category}/{group}/{name}/log/live/{date}.log
```

**查看日志：**
```bash
# 实时查看 master 日志
tail -f $KF_HOME/runtime/system/service/master/log/live/*.log

# 查看错误日志
grep ERROR $KF_HOME/runtime/*/log/live/*.log

# 查看特定组件日志
tail -f $KF_HOME/runtime/strategy/test/perf/log/live/*.log
```

### Session 分析

```bash
# 查看 session 统计
kfc journal sessions --tablefmt grid

# 导出详细数据
kfc journal show -i <session_id> -o analysis.csv

# 使用 pandas 分析
python3 << EOF
import pandas as pd
df = pd.read_csv('analysis.csv')
print(f"总帧数: {len(df)}")
print(f"平均延迟: {df['latency'].mean():.2f} ns")
print(f"最大延迟: {df['latency'].max():.2f} ns")
EOF
```

### 性能调优参数

**低延迟模式：**
```bash
# 添加 -x 参数
kfc run -x service master
```

**内存配置：**
- Journal page 大小默认 64MB
- 可在 CMake 配置中调整

**CPU 亲和性：**
```bash
# 绑定特定 CPU 核心
taskset -c 0-3 kfc run service master
```

## 常见问题

### Q1: Master 无法启动

**检查项：**
1. 端口是否被占用
2. KF_HOME 目录权限
3. 日志文件中的错误信息

**解决方法：**
```bash
# 清理旧数据
rm -rf $KF_HOME/runtime/system/service/master

# 重新启动
kfc run service master
```

### Q2: Apprentice 无法注册

**检查项：**
1. Master 是否正常运行
2. 网络连接是否正常
3. 配置文件是否正确

**解决方法：**
```bash
# 检查 master 进程
ps aux | grep master

# 查看 master 日志
tail -f $KF_HOME/runtime/system/service/master/log/live/*.log
```

### Q3: 性能不达标

**优化建议：**
1. 启用低延迟模式（-x 参数）
2. 使用 SSD 存储 journal
3. 调整系统参数（如文件描述符限制）
4. 减少日志输出级别

### Q4: 内存占用过高

**检查项：**
1. Journal page 是否累积过多
2. 是否有内存泄漏

**解决方法：**
```bash
# 清理旧 journal
kfc journal clean

# 定期归档
kfc journal archive
```

## 目录结构参考

```
$KF_HOME/
├── runtime/              # 运行时数据
│   ├── system/          # 系统进程
│   │   └── service/
│   │       ├── master/
│   │       │   ├── journal/
│   │       │   └── log/
│   │       └── ledger/
│   ├── md/              # 行情数据
│   ├── td/              # 交易数据
│   └── strategy/        # 策略数据
├── log/                 # 日志文件
├── archive/             # 归档数据
│   └── KFA-*.zip       # 日期归档
├── config/              # 配置文件
└── db/                  # 数据库文件
```

## 参考资料

- **官方文档**：https://docs.libkungfu.cc
- **GitHub 仓库**：https://github.com/kungfu-trader/kungfu
- **架构说明**：见 README.md

## 版本信息

- 功夫版本：2.4.77
- 文档更新日期：2026-03-13
