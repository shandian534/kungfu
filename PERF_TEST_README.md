# 易筋经性能测试使用说明

## 快速开始

### 1. 启动 Master

在运行测试前，需要先启动 master 进程：

```bash
export KF_HOME=/Users/shandian/kungfu
kfc run -c system -g master -n master &
```

### 2. 运行快速测试

验证环境和数据是否正常：

```bash
python3.9 perf_test_full.py --mode quick
```

### 3. 运行指定场景

运行场景 S1 和 S2（快速验证和顺序写入）：

```bash
python3.9 perf_test_full.py --mode scenario --scenarios 0,1
```

### 4. 运行所有场景

```bash
python3.9 perf_test_full.py --mode all
```

## 测试场景说明

| 索引 | 场景名称 | 文件数 | 批次 | 并行数 | 类型 |
|------|----------|--------|------|--------|------|
| 0 | S1_快速验证 | 10 | 1 | 1 | 顺序 |
| 1 | S2_顺序写入_小批量 | 100 | 1 | 1 | 顺序 |
| 2 | S3_顺序写入_中批量 | 100 | 10 | 1 | 顺序 |
| 3 | S4_顺序写入_大批量 | 100 | 50 | 1 | 顺序 |
| 4 | S5_并行写入_5进程 | 100 | 1 | 5 | 并行 |
| 5 | S6_并行写入_10进程 | 100 | 1 | 10 | 并行 |

## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--mode` | 测试模式: quick/all/scenario | scenario |
| `--scenarios` | 场景索引，逗号分隔 | 0,1 |
| `--kf-home` | KF_HOME 路径 | /Users/shandian/kungfu |

## 输出说明

### 控制台输出

测试过程中会显示：
- 场景名称和配置
- 处理进度
- 实时资源监控
- 测试结果汇总

### 结果文件

所有结果保存在 `/Users/shandian/kungfu/test_results/` 目录：

- `{test_name}_{timestamp}.json` - 单个测试的详细结果
- `test_summary_{timestamp}.csv` - 所有测试的汇总表

### 性能指标

| 指标 | 说明 |
|------|------|
| 总行数 | 写入的总数据条数 |
| 总耗时 | 测试运行时间（秒） |
| 平均延迟 | 单条数据写入平均时间（微秒） |
| 吞吐量 | 每秒写入数据条数 (ops) |

## 示例输出

```
==============================================================
=== 顺序写入测试 ===
CSV文件数: 100, 批次大小: 1
==============================================================
创建 apprentice...
初始化 apprentice...
Apprentice 注册成功!
开始资源监控...
开始写入数据...
已处理: 100/100 文件

==============================================================
测试结果:
  总行数: 45000
  总耗时: 12.34秒
  吞吐量: 3645 ops
  平均延迟: 274.22微秒
==============================================================
```

## 注意事项

1. **Master 必须先启动**：测试脚本依赖 master 进程运行
2. **路径问题**：确保 KF_HOME 环境变量设置正确
3. **数据目录**：默认使用 `/Users/shandian/kungfu/TRADE` 中的数据
4. **资源占用**：并行测试会创建多个进程，注意系统资源

## 故障排查

### Master socket 不存在

```
错误: Master socket 不存在: /path/to/pub.nn
```

解决：先启动 master 进程
```bash
export KF_HOME=/Users/shandian/kungfu
kfc run -c system -g master -n master &
```

### Apprentice 注册超时

```
[ error ] [apprentice.cpp:183#operator()] app register timeout
```

解决：检查 KF_HOME 路径是否一致，master 是否正常运行

### 数据目录不存在

```
错误: 交易数据目录不存在: /path/to/TRADE
```

解决：检查数据目录路径，或修改脚本中的 `trade_data_dir`
