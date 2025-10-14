# Web版性能诊断工具开发计划书

## 0. 项目目标与范围

- **目标**：在服务器上部署一套网页应用，实时/事后诊断**CPU 与进程**相关性能问题；支持主机与容器场景，兼顾“监控（长时序）+ 诊断（短期深挖）+ 剖析（代码级热点）”三层能力。
- **范围**：优先支持 Linux（内核 ≥ 4.14 优先；eBPF 建议 ≥ 5.x），后续可兼容 Kubernetes 节点与容器。
- **非目标（MVP 暂不做）**：分布式追踪（tracing）与应用日志聚合，仅预留接入（可通过 OpenTelemetry/OTLP 兼容）。

## 1. 使用的性能诊断工具（推荐组合）

> 监控与诊断通常需要“基础指标采集 + 深度内核/调度观测 + 持续剖析 + 可视化/告警”。下表给出推荐栈与用途。

| 层次 | 工具 | 用途 | 关键点/权限 | 参考 |
| --- | --- | --- | --- | --- |
| 主机/系统指标 | **Prometheus Node Exporter** | 暴露主机 CPU、负载、上下文切换、磁盘/网络等 **node_*** 系列指标，供 Prometheus 抓取 | 常规用户即可跑；按需开启 collector | 官方指南列出典型指标如 `node_cpu_seconds_total`、`node_load1` 等。 |
| 进程指标 | **process-exporter** | 以“进程名/匹配规则”聚合导出进程 CPU、内存、FD 等 | 读取 `/proc`；通过 YAML 规则分组 | 支持按命令行/正则分组监控特定进程。 |
| 容器指标（可选） | **cAdvisor** | 容器 CPU/内存/BlkIO/网络指标，原生 Prometheus 格式 | 容器/节点集成 | `/metrics` 原生支持 Prometheus 抓取。 |
| 深度调度/内核观测 | **BCC/eBPF 工具集**（`runqlen`、`runqlat`、`offcputime`、`biolatency` 等） | 采集**运行队列长度/延迟**、**Off-CPU 阻塞栈**、**块 I/O 延迟**等，发现 CPU 抢占/调度拥塞与等待瓶颈 | **需要 root 或 CAP_BPF/CAP_PERFMON**；注意开销 | BCC 收录大量可直接使用的诊断脚本与 man page。 |
| 内核态动态观测语言 | **bpftrace** | 更快编写临时 eBPF 脚本（直方图/热力图等） | 内核/权限同上 | 官方 reference & 示例展示直方图/延迟分布用法。 |
| 抽样剖析（持续） | **Grafana Pyroscope（eBPF agent）/Parca** | **持续 CPU/内存剖析**（pprof 格式），生成火焰图/冰柱图，定位代码级热点 | eBPF agent 需 root/host PID ns | Pyroscope/Parca 面向生产低开销剖析，支持 eBPF 采样与 Web UI。 |
| 采集/汇聚（可选） | **OpenTelemetry Collector**（Prometheus Receiver） | 统一接入 Prometheus 暴露的指标（含自研/第三方 exporter），再转发到存储/告警 | 可与 Prometheus 并存 | 架构与 Prometheus Receiver 说明。 |
| 剖析可视化（内嵌备用） | **speedscope** / **FlameGraph** | 在网页内浏览 pprof/火焰图 | 纯前端查看器可内嵌 | speedscope 为通用 Web 查看器；FlameGraph 项目提供生成脚本。 |
| 采样分析（一次性） | **Linux perf** | 进程/系统级采样+调用栈，离线 `perf.data` 分析 | 无内核改动；支持火焰图生成 | `perf record -a/-p` 采集，`perf report` 分析。 |

> **权限与内核要求**：bpftrace/BCC 通常需要较新的内核与特权（或 CAP_BPF/CAP_PERFMON/CAP_SYS_ADMIN 组合），主流发行版中默认仅对特权用户开放；生产上建议以最小权限运行。

## 2. 可以诊断的指标（优先 CPU/进程）

> 指标分为**监控（长时序）**与**诊断（按需短期采样/追踪）**两类。

### 2.1 主机级 CPU/调度（监控类）

- **CPU 利用率分解**：user/system/iowait/irq/softirq/idle —— 源自 `node_cpu_seconds_total` 及 `rate()`。
- **负载**：`node_load1/5/15`。
- **上下文切换速率**：`node_context_switches_total`（可求导得到速率）。
- **运行/阻塞进程数**：`node_procs_running`、`node_procs_blocked`（注意在极端场景下可能噪声较大）。
- **CPU 频率（可选）**：`node_cpu_scaling_frequency_hertz`/`node_cpu_frequency_hertz`（启用 cpufreq collector 后；多核机器需评估开销）。

### 2.2 进程级（监控类）

- **CPU 使用率/时间**、**线程数**、**打开文件句柄**、**RSS/VMS**、**I/O 读写速率**：通过 process-exporter（聚合到进程组）或自研 agent/psutil 获取；pidstat 也可用于校验与对比（`%CPU`、`minflt/s`、`majflt/s`、`cswch/s`、`nvcswch/s`、`kB_rd/s`、`kB_wr/s` 等）。

### 2.3 深度诊断（短期观测）

- **运行队列长度/占用率**：BCC `runqlen`（直方图/占用率），识别调度拥塞与负载不均。
- **调度等待（Run queue latency）**：`runqlat` 直方图，衡量任务从就绪到上 CPU 的延迟。
- **Off-CPU 阻塞时间与调用栈**：`offcputime` 显示线程被阻塞的原因与耗时（I/O、锁、缺页、调度等），补充 CPU 火焰图的盲区。
- **块设备 I/O 延迟分布**：`biolatency`（bpftrace/BCC 版本均有），识别 Cache 命中/未命中导致的双峰分布。
- **持续剖析（Profile）**：Pyroscope/Parca 采样 CPU（与内核栈），在 Web 中生成火焰图/冰柱图，支持时间区间对比与差异图。
- **一次性采样剖析**：`perf record/report` + FlameGraph 生成交互式 SVG 火焰图。

## 3. 可视化内容（图表设计）

> 采用 **时序 + 分布 + 拓扑/栈** 三类视图，配合“TopN 表格”和“诊断向导”。

1. **总览仪表盘（主机粒度）**
   - CPU 模式堆叠折线（user/system/iowait/irq/softirq/steal/idle）
   - 1/5/15 分钟负载对比条 & 阈值标线
   - 上下文切换速率折线、`procs_running/blocked` 微型趋势
   - CPU 频率（若开启 cpufreq）
     - *数据源：Node Exporter + PromQL。*
2. **进程总览**
   - **Top N 进程**：按 `%CPU`、RSS、I/O 读写速率、上下文切换速率排序的可分页表格
   - **进程 CPU 占用趋势**（支持按规则聚合，如 `nginx*`、`java -jar ...`）
     - *数据源：process-exporter。*
3. **调度深度页（诊断模式）**
   - **运行队列长度直方图**（`runqlen`），带 P50/P95 标注
   - **调度等待延迟直方图**（`runqlat`）
   - **Off-CPU 时间 Top 调用栈**（offcputime 的折叠表 + 可下载火焰图输入）
     - *数据源：BCC/BPF 任务一次性运行并缓存结果。*
4. **剖析页（持续剖析）**
   - **火焰图/冰柱图**（支持区间对比、差异上色）
   - 维度筛选：进程、容器/Pod、二进制、符号
     - *数据源：Pyroscope/Parca，内嵌查看组件或跳转。*
5. **容器视图（可选）**
   - 容器级 CPU/内存/BlkIO 时序、容器 Top 表格
     - *数据源：cAdvisor。*

> 图表实现建议采用 **Apache ECharts**（折线、直方图、热力图、数据缩放、百万数据量渐进渲染）。火焰图可嵌 speedscope（纯前端）。

## 4. 网页布局与使用方法

### 4.1 信息架构与布局

左侧主导航（示例）：

1. **总览**
2. **主机列表**（每台主机详情页：CPU/负载/上下文切换/进程 Top）
3. **进程总览**（跨主机聚合）
4. **调度深度**（`runqlen/runqlat/offcputime/biolatency` 一键触发+结果缓存）
5. **剖析**（Pyroscope/Parca 火焰图）
6. **告警**（阈值/静默/路由设置）
7. **设置**（目标管理、采集开关、权限）

**页面布局（示意）**

- 顶栏：时间范围选择器（Last 15m/1h/6h/1d + 自定义），刷新频率（5s/15s/1m）。
- 主区：卡片化面板（时序 + Top 表 + 诊断卡片）。
- 右侧抽屉：指标解释/PromQL/运行建议。

### 4.2 使用方法（运维与开发视角）

**（A）部署**

- **基础组件（Docker Compose/K8s）**：Prometheus（或 OTel Collector + 远端存储）、Node Exporter、process-exporter、（可选）cAdvisor、Web 应用（API + 前端）、（可选）Alertmanager、Pyroscope/Parca。
  - Node Exporter 暴露 `node_*` 指标供 Prometheus 抓取。
  - 若采用 OTel Collector，启用 **prometheusreceiver** 直接抓取 exporter 的 `/metrics`。
  - 告警用 **Alertmanager** 处理去重/分组/路由（邮件/IM/值班系统）。

**（B）接入主机**

1. 在目标主机运行 Node Exporter 与（可选）process-exporter。
2. 在平台“设置 → 目标管理”添加 `<host>:9100`（及 process-exporter 端口）。
3. 在“主机详情”页确认 CPU/负载等曲线有数据。

**（C）深度诊断**

- 在“调度深度”页**临时启动** BCC 工具（带时长/采样率参数）：
  - `runqlen`/`runqlat`：查看运行队列拥塞与调度等待（直方图）。
  - `offcputime`：抓阻塞调用栈，定位锁/IO 等等待源头。
  - `biolatency`：块设备 I/O 延迟分布，识别存储热点与长尾。
- **注意**：eBPF 任务需 root 或相应 CAP 能力；在高事件率工作负载上需控制开销（面板提示与采样阈值）。

**（D）持续剖析**

- 在“设置 → 剖析”中启用 **Pyroscope eBPF/Parca Agent**（host PID ns / 特权容器），在“剖析”页浏览火焰图，并支持**区间对比与差异高亮**。

## 5. 告警与阈值（示例）

- **CPU 持续高**：`sum by(instance)(1 - avg without(cpu)(rate(node_cpu_seconds_total{mode="idle"}[5m]))) > 0.85` 连续 10 分钟。
- **运行队列异常**：`node_load1 > cpu_cores * 1.5`（或 `runqlen` 分布 P95 超阈值 N 分钟，诊断模式下触发通知）。
- **上下文切换异常上升**：`rate(node_context_switches_total[5m])` 环比大幅上涨。
- **某进程 CPU 异常**：process-exporter 聚合的 `%CPU` 超阈值并持续。
- 告警通过 **Alertmanager** 分组路由至邮件/IM。

## 6. 技术架构与接口

**推荐架构（简化版）**

```
[Node Exporter]  [process-exporter]  [cAdvisor?]  [Pyroscope/Parca Agent?]  [BCC Jobs]
        \             |                   |                 |                   |
         --------------->  [Prometheus / OTel Collector(prometheusreceiver)]  -----> [TSDB/Profiles]
                                               |
                                            [Web API]  <----->  [Web UI(ECharts + speedscope)]
                                               |
                                          [Alertmanager]
```

- **Web API**：提供统一查询接口（封装 Prometheus HTTP API 的 query_range）、触发/管理 BCC 诊断任务、聚合剖析入口。
- **前端**：React/Next.js + ECharts；火焰图内嵌 speedscope。

## 7. 安全与性能开销

- **权限**：eBPF（BCC/bpftrace/Pyroscope eBPF/Parca Agent）需 root 或能力（CAP_BPF/CAP_PERFMON/CAP_SYS_ADMIN）；生产上建议**仅在诊断窗口**开启，并限制采样频率/时长。
- **内核要求**：bpftrace/BCC 建议新内核；bpftrace 文档建议使用较新发行版内核。
- **采集开销**：`runqlat/runqlen` 在高频调度场景下可能带来显著开销（UI 提醒“在预生产验证采样参数”）。
- **Node Exporter cpufreq collector**：在多核机器上可能增加 CPU 使用率，默认建议关闭，按需启用。

## 8. 开发计划（8–10 周、三阶段里程碑）

### 阶段 I（第 1–3 周）：MVP 监控闭环

- **后端**：Prometheus/或 OTel Collector（prometheusreceiver）部署；Web API（目标注册、PromQL 代理）。
- **Agent**：Node Exporter、process-exporter 接入；（可选）cAdvisor。
- **前端**：总览/主机详情/进程总览页面 + ECharts 图表。
- **告警**：Alertmanager 基础路由。
- **验收**：能在 1 秒～15 秒粒度查看 CPU/负载/进程 Top，告警能发出。

### 阶段 II（第 4–6 周）：深度诊断与剖析

- **BCC 诊断任务编排**：支持 `runqlen/runqlat/offcputime/biolatency` 一键运行、权限校验、结果持久化与下载。
- **剖析集成**：接入 Pyroscope 或 Parca，前端内嵌火焰图查看器（或跳转），支持区间 Diff。
- **验收**：能在 CPU 高时，一键进入调度页定位“队列/等待/阻塞来源”，并在剖析页定位函数级热点。

### 阶段 III（第 7–10 周）：易用性与稳健性

- **权限/审计**：只读/诊断操作分权；诊断任务审计日志。
- **性能与资源**：导入限流、诊断任务并发控制，TSDB 保留与下采样策略。
- **文档与演示数据**：内置 Demo 数据与指标解释面板。

## 9. 接口与数据模型（示例）

- `GET /api/hosts`：主机列表与可用性。
- `GET /api/query_range?expr=<PromQL>&start&end&step`：封装查询。
- `POST /api/diagnose/jobs`：创建 BCC 诊断任务（类型、目标、时长、采样率、过滤器）。
- `GET /api/diagnose/jobs/:id`：任务状态与结果（JSON + 文件）。
- `GET /api/profiles/...`：剖析数据查询/跳转。

## 10. 运维与最佳实践

- **分层开关**：监控（常开）、剖析（低频常开或故障期开启）、BCC（仅在定位期短时开启）。
- **基线与阈值**：为上下文切换、负载、进程 CPU 建立**业务时段基线**，避免误报。
- **容器场景**：优先用 cAdvisor 暴露容器指标，并将剖析维度带上容器/Pod 标签。

## 11. 参考资料（关键出处）

- **Node Exporter 指标与使用**：Prometheus 官方指南。
- **PromQL `rate()` 等函数**：Prometheus 函数文档。
- **process-exporter**：项目说明与配置规则。
- **BCC/eBPF 工具**：官方站点与具体工具 man page（`runqlen`、`runqlat`、`offcputime`、`biolatency`）。
- **bpftrace 文档**：参考与示例。
- **Pyroscope/Parca（持续剖析）**：官方介绍与 eBPF agent。
- **Alertmanager**：概览与配置。
- **Linux perf**：RHEL 文档与 man page。
- **eBPF 权限/内核要求**：bpftrace 安装建议与 RHEL 关于 eBPF 权限说明。

---

以上计划书即为后续开发与落地的“蓝图”：

- **先以 Node Exporter + process-exporter + Prometheus + WebUI** 完成监控闭环；
- 再通过 **BCC 深度诊断** 与 **Pyroscope/Parca 持续剖析** 形成“**指标 → 现象 → 根因**”的闭环。

如需，我可以把上述方案落为**部署清单（Docker Compose/K8s Manifests）**与**前端原型图**，并补充一批**PromQL 模板**（CPU 利用率、上下文切换、Top N 进程、负载/核心数归一化等）。
