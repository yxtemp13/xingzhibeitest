# Web 性能诊断工具

本仓库提供一个可运行的 Web 版性能诊断工具，实现了《Web版性能诊断工具开发计划书》中规划的关键能力：

- **监控指标查询**：封装 Prometheus `query_range` 接口，前端使用 ECharts 展示 CPU 指标趋势。
- **诊断任务编排**：模拟 `runqlen`、`runqlat`、`offcputime`、`biolatency` 等 BCC 工具的执行流程，支持启动、查看状态与结果。
- **持续剖析视图**：提供火焰图元数据列表，便于跳转外部火焰图或结合 speedscope 等工具查看。
- **一体化前端**：纯静态前端基于 PicoCSS + ECharts + 原生 JS，覆盖主机概览、CPU 趋势、诊断任务和剖析列表四大分区。

> 原始规划文档位于 [`docs/plan.md`](docs/plan.md)。

## 目录结构

```
backend/            FastAPI 应用实现
  app/
    config.py       配置加载与模型
    diagnostics.py  诊断任务调度器
    main.py         FastAPI 入口
    models.py       Pydantic 数据模型
    profiles.py     持续剖析数据访问
    prometheus.py   Prometheus 查询封装
  scripts/
    simulate_bcc_job.py  BCC 任务模拟脚本
frontend/           静态页面与交互脚本
  index.html
  main.js
config.yaml         应用配置（主机、Prometheus、诊断任务）
data/mock/          Mock 数据（Prometheus & Profile）
data/jobs/          诊断任务临时输出
```

## 快速开始

1. **准备 Python 环境**（Python 3.10+）：

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-dev.txt
   ```

2. **启动后端服务**：

   ```bash
   uvicorn backend.app.main:app --reload
   ```

   默认监听 `http://127.0.0.1:8000`，根路径会自动跳转到前端页面。

3. **打开前端页面**：浏览器访问 `http://127.0.0.1:8000/frontend/index.html` 即可。

> 如需对接真实 Prometheus，可在 `config.yaml` 中配置 `prometheus.base_url` 并移除 `mock_data_dir`。

## API 概览

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| GET | `/api/hosts` | 返回配置中的主机列表 |
| GET | `/api/query_range` | 代理 Prometheus `query_range`，支持 mock 数据 |
| POST | `/api/diagnose/jobs` | 创建诊断任务（模拟执行） |
| GET | `/api/diagnose/jobs` | 返回所有任务状态 |
| GET | `/api/diagnose/jobs/{id}` | 查询单个任务详情 |
| GET | `/api/profiles` | 返回持续剖析概要列表 |
| GET | `/api/profiles/{id}` | 返回指定剖析详情 |
| GET | `/healthz` | 健康检查 |

## 配置说明

- **hosts**：前端展示的主机与标签。
- **prometheus**：
  - `base_url`：Prometheus 服务地址。
  - `mock_data_dir`：若存在则优先使用其中的 JSON 数据，便于离线演示。
- **diagnostics.job_types**：定义任务名称、脚本路径以及输出模式。默认脚本会生成模拟数据，可替换为真实 BCC 脚本。
- **profiles.data_file**：持续剖析元数据来源，格式为 JSON 数组。

## 开发与测试

运行 FastAPI 单元测试：

```bash
pytest
```

测试覆盖配置加载、Prometheus mock 查询、诊断任务流程以及剖析列表接口。

## 扩展建议

- 将 `simulate_bcc_job.py` 替换为实际的 eBPF/BCC 脚本，并在前端展示具体结果（如直方图、火焰图链接）。
- 对接真实 Prometheus 与 Pyroscope/Parca 服务，利用现有 API 模型进行扩展。
- 引入身份认证与操作审计，满足生产环境的权限分级需求。

