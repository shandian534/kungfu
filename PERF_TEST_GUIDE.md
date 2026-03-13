# 易筋经性能测试步骤说明

本文档提供详细的测试步骤，帮助你完成易筋经时间序列数据库的性能测试。

## 测试环境准备

### 1. 确认功夫核心库已构建

```bash
# 检查核心库是否存在
ls -la /Users/shandian/out/kungfu/framework/core/dist/kfc/

# 应该看到以下文件：
# - kfc (可执行文件)
# - kungfu_node.node
# - pykungfu.cpython-39-darwin.so
# - Python (可执行文件)
# - 其他依赖库
```

### 2. 设置环境变量

```bash
# 设置功夫数据目录
export KF_HOME=~/kungfu_perf_test

# 设置日志级别（可选，info级别可减少日志输出）
export KF_LOG_LEVEL=info

# 创建测试目录
mkdir -p $KF_HOME
```

### 3. 安装Python依赖

```bash
# 安装必要的Python包
pip3 install pandas matplotlib psutil

# 或者使用pip
pip install pandas matplotlib psutil
```

## 测试脚本说明

测试脚本位置：`/Users/shandian/out/kungfu/perf_test.py`

### 脚本功能

- **ResourceMonitor**: 监控CPU和内存使用率
- **TradeDataSelector**: 从真实交易数据目录随机选择CSV文件
- **SequentialWriteTest**: 顺序写入测试
- **PerformanceReporter**: 生成测试报告和图表

### 支持的测试模式

```bash
# 快速验证测试（10个文件）
正确：
在 A窗口
在项目主目录下（kungfu)
export KF_HOME=/Users/shandian/kungfu 
 kfc run -c system -g master -n master &
 ps -ef|grep kfc 
 ps -ef|grep master  
 
 在 B窗口
 sudo /usr/local/bin/python3.9 /Users/shandian/out/kungfu/perf_test.py
跳过 master 启动，使用已运行的实例
[DEBUG] KF_HOME: /Users/shandian/kungfu/runtime
[DEBUG] Master location: system/master/master/live
[DEBUG] Master pub.nn path: /Users/shandian/kungfu/runtime/system/master/master/nn/live/pub.nn
[DEBUG] Apprentice location: strategy/perf_test/app/live
[DEBUG] Master socket directory: /Users/shandian/kungfu/runtime/system/master/master/nn/live
[DEBUG] Master socket exists: False
[DEBUG] Socket files in directory: []
[DEBUG] Creating apprentice with low_latency=True
初始化 apprentice...
[DEBUG] Starting apprentice.setup() - this will try to connect to master and register...
Apprentice 注册成功!
写入完成，耗时: 6.08秒




# 单次测试（指定文件数）
python3 perf_test.py test 100      # 测试100个文件
python3 perf_test.py test 1000     # 测试1000个文件
python3 perf_test.py test 5000     # 测试5000个文件

# 批量测试（指定批次大小）
python3 perf_test.py test 1000 10  # 测试1000个文件，批次大小10
python3 perf_test.py test 1000 100 # 测试1000个文件，批次大小100
```

## 测试步骤

### 步骤1：快速验证测试

首先运行快速测试，验证环境配置是否正确。

```bash
# 进入项目目录
cd /Users/shandian/out/kungfu

# 运行快速测试（10个CSV文件）
python3 perf_test.py quick
```

**预期输出**：
```
============================================================
易筋经性能测试 - 快速验证
============================================================
发现 7034 个CSV文件
随机选择了 10 个文件

选择的文件（前3个）：
  000001.csv
  000002.csv
  000004.csv

=== 顺序写入测试 ===
CSV文件数: 10, 批次大小: 1
总耗时: X.XX秒
处理行数: XXX
吞吐量: XXX ops
平均延迟: XXX.XX微秒
结果已保存到: ~/kungfu_perf_test/test_results/sequential_write_YYYYMMDD_HHMMSS.json
图表已保存: ~/kungfu_perf_test/reports/sequential_write_resource_YYYYMMDD_HHMMSS.png

============================================================
快速测试完成！
============================================================
```

**验证要点**：
- ✅ 能够正常导入功夫核心库
- ✅ 能够读取CSV文件
- ✅ 能够创建writer并写入数据
- ✅ 能够监控CPU和内存
- ✅ 能够生成图表

如果快速测试失败，请检查：
1. 功夫核心库路径是否正确
2. Python依赖是否安装完整
3. KF_HOME目录是否有写权限

### 步骤2：小规模测试

快速验证通过后，运行小规模测试。

```bash
# 测试100个文件
python3 perf_test.py test 100
```

观察输出中的：
- 总耗时
- 吞吐量
- 平均延迟
- CPU和内存使用情况

### 步骤3：中等规模测试

```bash
# 测试1000个文件
python3 perf_test.py test 1000
```

### 步骤4：大规模测试

```bash
# 测试5000个文件（最大规模）
python3 perf_test.py test 5000
```

### 步骤5：批量测试（可选）

如果需要测试不同批次大小的影响：

```bash
# 测试1000个文件，批次大小10
python3 perf_test.py test 1000 10

# 测试1000个文件，批次大小100
python3 perf_test.py test 1000 100
```

## 测试结果查看

### 1. 测试结果文件

位置：`~/kungfu_perf_test/test_results/`

```bash
# 查看所有测试结果
ls -lh ~/kungfu_perf_test/test_results/

# 查看某个测试结果
cat ~/kungfu_perf_test/test_results/sequential_write_*.json | python3 -m json.tool
```

### 2. 资源监控图表

位置：`~/kungfu_perf_test/reports/`

```bash
# 查看生成的图表
ls -lh ~/kungfu_perf_test/reports/

# 在macOS上打开图表
open ~/kungfu_perf_test/reports/*.png
```

图表内容包括：
- **CPU使用率曲线**（红色）：显示测试期间CPU占用情况
- **内存使用率曲线**（蓝色）：显示测试期间内存占用情况

### 3. 查看实时资源使用

在测试运行期间，可以在另一个终端监控资源：

```bash
# 监控CPU和内存
top -pid $(pgrep -f perf_test.py)

# 或使用htop（如果已安装）
htop -p $(pgrep -f perf_test.py)
```

## 性能指标说明

### 1. 吞吐量（Throughput）
- **含义**：每秒处理的数据条数
- **单位**：ops (operations per second)
- **期望值**：根据硬件配置，通常在几百到几千之间

### 2. 平均延迟（Average Latency）
- **含义**：单条数据从读取到写入的平均时间
- **单位**：微秒（μs）
- **期望值**：越低越好，通常在几百微秒左右

### 3. CPU使用率
- **含义**：测试期间CPU的平均占用率
- **单位**：百分比（%）
- **分析**：
  - 如果CPU使用率很低（<30%），说明系统可能有其他瓶颈（如磁盘I/O）
  - 如果CPU使用率很高（>90%），说明CPU是性能瓶颈

### 4. 内存使用率
- **含义**：测试期间内存的平均占用率
- **单位**：百分比（%）
- **分析**：
  - 观察内存是否稳定增长（可能存在内存泄漏）
  - 观察峰值内存使用量

## 常见问题排查

### 问题1：导入错误

```
ImportError: cannot import name 'longfist'
```

**解决方案**：
```bash
# 检查核心库路径
ls -la /Users/shandian/out/kungfu/framework/core/dist/kfc/

# 如果路径不对，修改脚本中的kungfu_core_path变量
# 或者设置PYTHONPATH
export PYTHONPATH=/Users/shandian/out/kungfu/framework/core/dist/kfc:$PYTHONPATH
```

### 问题2：找不到CSV文件

```
发现 0 个CSV文件
```

**解决方案**：
```bash
# 检查数据目录
ls /Users/shandian/kungfu/TRADE/*.csv | wc -l

# 如果目录不对，修改脚本中的trade_data_dir变量
```

### 问题3：权限错误

```
Permission denied: '/Users/shandian/kungfu_perf_test'
```

**解决方案**：
```bash
# 创建目录并设置权限
mkdir -p ~/kungfu_perf_test
chmod 755 ~/kungfu_perf_test
```

### 问题4：内存不足

```
MemoryError: ...
```

**解决方案**：
- 减少测试文件数量
- 关闭其他占用内存的程序
- 增加系统交换空间

## 测试场景建议

根据不同的测试目的，选择合适的测试规模：

### 场景1：功能验证
```bash
python3 perf_test.py quick  # 10个文件
```

### 场景2：基准测试
```bash
python3 perf_test.py test 100   # 100个文件
python3 perf_test.py test 1000  # 1000个文件
```

### 场景3：压力测试
```bash
python3 perf_test.py test 3000  # 3000个文件
python3 perf_test.py test 5000  # 5000个文件（接近最大）
```

### 场景4：批量性能对比
```bash
# 测试不同批次大小的影响
python3 perf_test.py test 1000 1    # 批次大小1
python3 perf_test.py test 1000 10   # 批次大小10
python3 perf_test.py test 1000 100  # 批次大小100
```

## 下一步

测试完成后，你可以：

1. **分析结果**：查看生成的JSON和图表文件
2. **对比性能**：比较不同场景下的性能指标
3. **优化系统**：根据瓶颈进行针对性优化
4. **扩展测试**：添加更多测试场景（如并行写入测试）

## 技术支持

如果遇到问题，请检查：
1. 功夫核心库是否正确构建
2. Python版本是否为3.9
3. 所有依赖是否正确安装
4. 系统资源是否充足（磁盘空间、内存）

测试脚本位置：`/Users/shandian/out/kungfu/perf_test.py`
测试方案文档：`/Users/shandian/out/kungfu/YIJINJING_PERFORMANCE_TEST_PLAN.md`
