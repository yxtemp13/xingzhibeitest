# 网页版服务器性能诊断工具

该项目提供一个可直接部署在 Linux 主机上的轻量级网页诊断工具。后端基于 FastAPI + psutil，能够采集主机与进程指标、给出健康评估，并通过简单的网页展示核心信息。

![系统概览页面示意](app/static/index.html)

## 功能特性

- **系统指标采集**：CPU 利用率、负载、内存、Swap、磁盘分区、磁盘 IO、网络 IO、温度等信息。
- **进程热点定位**：列出按 CPU/内存排序的 TopN 进程，展示 PID、名称、CPU%、内存%、线程数、启动时间。
- **进程详情**：通过 `/api/processes/{pid}` 查看指定进程的 CPU 时间、内存占用、线程、打开文件、网络连接等。
- **动态诊断**：提供 CPU 与磁盘的时间序列采样接口，可用于持续观察资源波动。
- **健康评估**：根据采集结果生成中文诊断建议与严重级别，帮助快速识别潜在风险。
- **网页总览**：内置简洁的前端页面（React-free），无需额外构建即可查看系统概览、健康评估与进程列表。

## 快速开始

1. **安装依赖**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **启动服务**

   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

3. **访问页面**

   浏览器打开 `http://<服务器IP>:8000/`，即可查看实时诊断信息。接口以 REST 形式提供，可被外部系统调用或二次开发。

## API 一览

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| GET | `/api/system` | 获取系统级指标快照，支持 `sample_duration` 参数控制 CPU 采样时间。 |
| GET | `/api/processes` | 获取按 CPU 或内存排序的 Top 进程，支持 `limit`、`sort_by` 参数。 |
| GET | `/api/processes/{pid}` | 查看指定进程的详细信息（线程、打开文件、连接、内存等）。 |
| GET | `/api/diagnostics/cpu` | 采样一段时间的 CPU 使用率序列。 |
| GET | `/api/diagnostics/disk` | 采样磁盘读写增量序列。 |
| GET | `/api/diagnostics/analysis` | 返回系统指标与自动化健康评估。 |

## 目录结构

```
.
├── app
│   ├── main.py          # FastAPI 应用入口
│   └── static
│       └── index.html   # 内置前端页面
├── diagnostic_tool
│   ├── __init__.py
│   ├── analyzer.py      # 健康评估逻辑
│   ├── processes.py     # 进程数据采集
│   └── system.py        # 系统级指标采集
└── requirements.txt
```

## 后续拓展建议

- 将静态页面替换为 React/Vue 等更丰富的前端框架，实现时序图、火焰图等高级可视化。
- 集成 Prometheus、Alertmanager 作为长期指标存储与告警系统。
- 对接 eBPF、perf、语言运行时（pprof/JFR 等）实现更深入的剖析能力。
- 增加用户登录与权限控制，适用于多租户或生产环境。

## 许可证

本项目以 MIT 许可证开源，欢迎二次开发与贡献。
