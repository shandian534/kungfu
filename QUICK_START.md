# 易筋经性能测试 - 一键测试指南

## 🚀 快速开始（三步走）

### 步骤 1：确保 Master 运行

```bash
# 检查 Master 是否运行
pgrep -f "kfc run.*master"

# 如果没有，启动它
export KF_HOME=/Users/shandian/kungfu
kfc run -c system -g master -n master &
```

---

### 步骤 2：选择运行方式

#### 方式 A：运行单个场景（快速测试）

```bash
# 运行场景 0（最快，约 15 秒）
python3.9 perf_test_v2.py --scenario 0

# 查看所有场景
python3.9 perf_test_v2.py --help
```

#### 方式 B：批量运行所有场景（完整测试）

```bash
# 使用 Shell 脚本（推荐）
./run_all_scenarios_v2.sh

# 或使用 Python 脚本
python3.9 run_all_scenarios_v2.py
```

---

### 步骤 3：查看结果

```bash
# 结果目录
cd /Users/shandian/kungfu/test_results

# 查看图表
open sequential_write_*.png
```

---

## 📊 20 个测试场景

| 索引 | 场景名称 | 说明 |
|------|----------|------|
| 0-3 | S1-S4 顺序写入 | 10/1000/3000/5000 文件，每次 1 个 |
| 4-11 | B10/B100 批量写入 | 批量 10/100，文件数 10/1000/3000/5000 |
| 12-19 | P5/P10 并行写入 | 并行 5/10 进程，文件数 10/1000/3000/5000 |

**预估总耗时：** 3-5 小时（20个场景）

---

## 🛠️ 常用命令

### 清理测试数据

```bash
# 清理 journal 文件
./cleanup_test.sh

# 或手动清理
rm -rf /Users/shandian/kungfu/runtime/strategy/perf_test/app/journal/live/*
```

### 后台运行

```bash
# 使用 nohup
nohup ./run_all_scenarios_v2.sh > test_run.log 2>&1 &

# 查看进度
tail -f test_run.log
```

### 单独重跑失败场景

```bash
# 例如重跑场景 5
python3.9 perf_test_v2.py --scenario 5
```

---

## ⚠️ 注意事项

1. **磁盘空间：** 确保至少 10GB 可用空间
2. **Master 必须运行：** 所有测试需要 Master 进程
3. **Timeout 警告：** 可以忽略的框架级提示
4. **中途停止：** Ctrl+C 停止，已完成的结果会保留

---

## 📁 输出文件

```
test_results/
├── sequential_write_S1_20260313_234500/
│   ├── metrics.json          # 性能指标
│   ├── journal_info.txt      # 文件信息
│   └── resource_chart.png    # 资源监控图表
└── ...
```

---

## 🔧 故障排查

### 问题：Master 进程未运行

```bash
export KF_HOME=/Users/shandian/kungfu
kfc run -c system -g master -n master &
```

### 问题：权限错误

```bash
# 删除并重新创建结果目录
sudo rm -rf /Users/shandian/kungfu/test_results
mkdir -p /Users/shandian/kungfu/test_results
```

### 问题：Timeout 错误

可以忽略，这是框架级的竞态条件，不影响测试结果。

---

## 📖 更多信息

- 详细使用说明：`PERF_TEST_V2_README.md`
- 批量运行说明：`BATCH_RUN_README.md`
- 测试计划：`YIJINJING_PERFORMANCE_TEST_PLAN.md`
