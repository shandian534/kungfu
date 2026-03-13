# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 功夫核心库

功夫（Kungfu）是为量化交易者设计的开源交易执行系统，提供微秒级系统响应、支持 Python/C++ 策略编写、跨平台运行。

### 系统架构

功夫采用模块化架构，主要分为以下几个层次：

**后台核心（C++）：**
- **longfist**（长拳）：金融交易数据格式定义，提供 C++/Python/JavaScript/SQLite 序列化支持
  - 头文件位于：`framework/core/src/include/kungfu/longfist/`
- **yijinjing**（易筋经）：超低延迟时间序列内存数据库，纳秒级时间精度
  - 头文件位于：`framework/core/src/include/kungfu/yijinjing/`
  - 实现 journal、page、frame 等核心数据结构
- **wingchun**（咏春）：策略执行引擎，提供策略开发接口
  - 头文件位于：`framework/core/src/include/kungfu/wingchun/`
  - 包含 broker（柜台对接）、book（账本管理）、strategy（策略引擎）

**策略接口：**
- **Python 绑定**：`framework/core/src/bindings/python/`
  - 暴露 yijinjing、wingchun、longfist 的 Python 接口
  - Python 模块位于：`framework/core/src/python/kungfu/`
- **Node.js 绑定**：`framework/core/src/bindings/node/`
  - 提供 Node.js addon 接口

**前端 UI（Node.js）：**
- **Electron 主进程**：`framework/app/src/main/`
- **Vue 渲染进程**：`framework/app/src/renderer/`
- **API 层**：`framework/api/` 提供 IPC 桥接和数据处理
- **CLI 工具**：`framework/cli/` 提供命令行接口

**扩展模块：**
- **XTP 扩展**：`extensions/xtp/` 提供 XTP 柜台对接实现
- **模拟交易**：`extensions/sim/` 提供模拟交易环境

### 开发命令

**完整构建流程：**
```bash
yarn install --frozen-lockfile  # 安装依赖（必须用 git clone 获取代码）
yarn build                      # 构建所有组件
yarn package                    # 打包应用
```

**清理和重建：**
```bash
yarn clean                      # 清理构建产物
yarn rebuild                    # 完全重新构建（clean + build）
```

**针对性构建：**
```bash
yarn build:core                 # 仅构建核心库
yarn rebuild:core               # 重新构建核心库
yarn build:app                  # 仅构建应用
yarn build:cli                  # 仅构建 CLI
```

**运行应用：**
```bash
yarn app                         # 启动图形界面应用
yarn cli                         # 启动命令行工具
yarn dev                         # 开发模式启动
```

**Python 相关：**
```bash
yarn workspace @kungfu-trader/kungfu-core poetry:lock   # 更新 Poetry 锁文件
yarn workspace @kungfu-trader/kungfu-core poetry:clear  # 清理 Poetry 缓存
```

### 工作区结构

项目使用 Yarn Workspaces 管理多个子包：

- `framework/core` - C++ 核心库及 Python/Node.js 绑定
- `framework/api` - JavaScript API 和 IPC 桥接
- `framework/app` - Electron 应用（Vue.js 前端）
- `framework/cli` - 命令行工具
- `developer/toolchain` - 构建工具链
- `developer/sdk` - SDK 开发包
- `extensions/*` - 柜台扩展（xtp、sim 等）
- `examples/*` - 示例策略和操作符
- `artifact` - 最终打包产物

### 关键技术点

**构建系统：**
- 使用 CMake + CMake-js 构建 C++ 组件
- 使用 Poetry 管理 Python 依赖
- 使用 Yarn Workspaces 管理 JavaScript/TypeScript 依赖

**Python 版本：**
- 目标版本：Python 3.9
- Poetry 配置：`framework/core/pyproject.toml`

**二进制分发：**
- 预编译二进制从 `https://prebuilt.libkungfu.cc` 下载
- 配置在各包的 `package.json` 的 `binary` 字段

### 临时文件位置

编译过程会产生以下临时文件：
```
node_modules
**/node_modules
**/build
**/dist
```

系统级临时文件：
```
$HOME/.conan                        # C++ 依赖包
$HOME/.cmake-js                     # C++ 依赖包
$HOME/.virtualenvs                  # Python 依赖（Windows）
$HOME/.local/share/virtualenvs      # Python 依赖（Unix）
```

### 文档和资源

- 项目文档：https://docs.libkungfu.cc
- 官方网站：https://www.kungfu-trader.com
- GitHub：https://github.com/kungfu-trader/kungfu
