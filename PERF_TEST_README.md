# 易筋经性能测试使用说明

## ⚠️ 重要限制

**每次只能运行一个场景**，因为功夫框架限制每个进程只能有一个 hero 实例。

## 快速开始

### 1. 启动 Master

在运行测试前，需要先启动 master 进程：

```bash
export KF_HOME=/Users/shandian/kungfu
kfc run -c system -g master -n master &
```

### 2. 运行快速测试

验证环境和数据是否正常（10个文件）：

```bash
python3.9 perf_test_full.py --mode quick
```

### 3. 运行指定场景

```bash
# 场景 0: 快速验证 (10文件)
python3.9 perf_test_full.py --scenario 0

# 场景 1: 小批量顺序写入 (100文件)
python3.9 perf_test_full.py --scenario 1

# 场景 2: 中批量顺序写入 (100文件, 批次10)
python3.9 perf_test_full.py --scenario 2

# 场景 4: 并行写入 5进程 (100文件)
python3.9 perf_test_full.py --scenario 4

# 场景 5: 并行写入 10进程 (100文件)
python3.9 perf_test_full.py --scenario 5
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
| `--mode` | 测试模式: quick/scenario | scenario |
| `--scenario` | 场景索引 (0-5) | 0 |
| `--kf-home` | KF_HOME 路径 | /Users/shandian/kungfu |

## 批量运行多个场景

由于框架限制，需要分别运行每个场景：

```bash
#!/bin/bash
# 运行所有场景的脚本

for i in 0 1 2 3 4 5; do
    echo "运行场景 $i..."
    python3.9 perf_test_full.py --scenario $i
    echo "场景 $i 完成，等待 3 秒..."
    sleep 3
done

echo "所有场景完成！"
```

保存为 `run_all.sh`，然后执行：
```bash
chmod +x run_all.sh
./run_all.sh
```

## 输出说明

### 控制台输出

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

### 结果文件

保存在 `/Users/shandian/kungfu/test_results/`：
- `sequential_write_YYYYMMDD_HHMMSS.json` - 详细结果（JSON格式）

### 性能指标

| 指标 | 说明 |
|------|------|
| 总行数 | 写入的总数据条数 |
| 总耗时 | 测试运行时间（秒） |
| 平均延迟 | 单条数据写入平均时间（微秒） |
| 吞吐量 | 每秒写入数据条数 (ops) |

## 故障排查

### Master socket 不存在

```
错误: Master socket 不存在: /path/to/pub.nn
```

**解决**：先启动 master
```bash
export KF_HOME=/Users/shandian/kungfu
kfc run -c system -g master -n master &
```

### Apprentice 注册超时

```
[ error ] [apprentice.cpp:183#operator()] app register timeout
```

**解决**：检查 KF_HOME 路径一致性
```bash
# 确保 master 和测试使用相同的路径
export KF_HOME=/Users/shandian/kungfu
```

### 只能运行一个场景

```
kungfu can only have one hero instance per process
```

**解决**：每次运行后退出，下次运行会启动新进程。使用批量脚本运行多个场景。

### 数据目录不存在

```
错误: 交易数据目录不存在: /path/to/TRADE
```

**解决**：检查数据目录或修改 `kf_home` 参数
```bash
python3.9 perf_test_full.py --kf-home /your/kungfu/path --scenario 0
```
