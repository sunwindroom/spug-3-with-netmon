# spug 3.0 · IT资源监控（apps.netmon）设计与集成说明

## 1. 背景与现状分析

已完整拉取并分析 `openspug/spug` 3.0 分支源码（Django + DRF风格自研框架 + React/antd/bizcharts + APScheduler/Redis队列架构）。结论：

spug 自带的 `apps/monitor` 是**存活探测**工具：站点/端口/进程/脚本/Ping 五种布尔型检测，触发阈值后发通知。它**不提供**：

| 能力 | spug 3.0 现状 | 本次交付 |
|---|---|---|
| 统一IT资源台账（网络设备/服务器/存储/中间件/应用） | 无（仅主机管理，无网络设备概念） | `Device` 模型 + 分类/分组 |
| 拓扑关系与可视化 | 无 | `Link` 模型 + SVG拓扑图 |
| 指标级实时采集（CPU/内存/磁盘/网卡/时延） | 无（仅布尔存活） | Ping/SNMP/Agent(SSH) 采集器 |
| 数据处理与异常检测 | 无 | 静态阈值 + 3-sigma动态基线 |
| 实时大屏 | 无 | 总览大屏（状态分布、集群均值、TOP异常） |
| 自动发现 | 无 | 网段扫描 + 端口探测 + 一键导入 |
| 报表统计分析 | 无 | 定时/手动生成 xlsx 报表（含图表） |

## 2. 参考的行业产品与借鉴点

- **Zabbix / LibreNMS / Cacti**（开源网管）：SNMP标准MIB采集思路、阈值触发机制、拓扑自动发现
- **PRTG / SolarWinds NPM / WhatsUp Gold**（商业网管）：实时大屏"状态色块+图标"的直观呈现方式
- **Grafana**：时序数据可视化交互（多时间粒度切换、悬浮提示）
- **ServiceNow ITOM / BMC Helix / 蓝鲸监控**：CMDB化的资源台账 + 事件（Anomaly）管理闭环（未处理→已确认→已恢复）
- **禅道/简道云类报表思维**：周期性报表订阅、异常次数与可用率统计

## 3. 总体架构

```
                     ┌───────────────────────────┐
                     │   React 前端 (pages/netmon) │
                     │ 总览大屏/拓扑/台账/异常/发现/报表 │
                     └──────────────┬────────────┘
                                    │ REST (/netmon/*)
                     ┌──────────────▼────────────┐
                     │      apps/netmon/views.py   │
                     └──────────────┬────────────┘
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
┌───────▼────────┐         ┌────────▼────────┐         ┌────────▼────────┐
│ scheduler.py     │         │ collectors.py    │         │ anomaly.py       │
│ APScheduler       │──push──▶│ Ping/SNMP/Agent  │──写入──▶│ 阈值 + 3-sigma    │
│ 按设备周期投递任务  │  Redis  │                  │ 时序表  │  基线检测         │
└───────────────────┘  队列   └──────────────────┘         └────────┬────────┘
                                                                      │触发
        ┌──────────────────┐         ┌──────────────────┐   ┌───────▼────────┐
        │ discovery.py       │         │ reports.py         │   │ apps.notify      │
        │ 网段扫描/自动发现   │         │ xlsx统计报表(图表)  │   │ 通知联动          │
        └──────────────────┘         └──────────────────┘   └─────────────────┘
```

采集/调度完全复用 spug 已有的 **APScheduler + Redis队列 + 共享worker线程池** 模式（与 `apps/monitor`、`apps/schedule` 一致），未引入 Celery 等新中间件，保证与现有运维方式（supervisor 管理多进程）一致。

## 4. 数据模型（`apps/netmon/models.py`）

- `NetGroup`：资源分组（业务/机房），供拓扑与报表按范围统计
- `Device`：统一资源台账（服务器/交换机/路由器/防火墙/负载均衡/存储/数据库/中间件/应用/其他），支持三种采集方式：`ping`｜`snmp`｜`agent`（复用已纳管主机的 SSH 凭据，无需重复配置）
- `Link`：拓扑连线（物理/逻辑），可标注带宽
- `MetricRecord`：时序指标（cpu/memory/disk/net_in/net_out/rtt/loss），轻量内置存储；**生产环境建议后续对接 Prometheus + Grafana 或 InfluxDB 做长周期归档**，本次实现的表结构可平滑迁移
- `AlertRule`：静态阈值规则（>、>=、<、<=、==，支持连续N次触发）
- `AnomalyEvent`：异常事件（阈值型/3-sigma型），状态机 未处理→已确认→已恢复
- `Report` / `ReportRecord`：报表定义与生成历史

## 5. 四项需求的对应实现

### 5.1 IT网络资源一体化监控与可视化
- `Device`/`Link` 统一建模网络设备、服务器、存储、中间件、应用等异构资源
- 拓扑视图（`Topology.js`）用 SVG 绘制节点+连线，无需引入 D3/G6 等新依赖，颜色标识健康状态，点击节点直接查看历史曲线

### 5.2 实时图形界面 + 简明图标
- `Overview.js` 总览大屏：设备总数/正常/告警/严重/离线统计卡片、健康状态环形图、集群CPU/内存仪表盘、近15分钟异常列表，10秒自动刷新
- 拓扑图使用 Emoji 图标区分设备类型（🖥️服务器 🔀交换机 📡路由器 🛡️防火墙 …），无需额外图片资源

### 5.3 数据采集/处理/分析/异常检测
- `collectors.py`：Ping时延丢包、SNMP标准MIB（HOST-RESOURCES-MIB/IF-MIB）、Agent(SSH)三种方式全覆盖
- `anomaly.py`：静态阈值规则 + **3-sigma动态基线**（滚动均值/标准差，无需人工为每个指标设定阈值，覆盖"没有统一标准"的场景），异常事件自动联动 `apps.notify` 通知
- `DeviceDetail.js`：分设备/分指标的历史曲线（30分钟/1小时/6小时切换），满足不同业务场景的展示粒度需求

### 5.4 报表管理：统计分析与自动发现
- `reports.py`：基于项目已引入的 `openpyxl` 生成含图表的 xlsx 报表（总览/设备明细/异常明细三张表）
- `gen_netmon_reports` 管理命令：可加入 crontab，按日报/周报/月报周期自动生成并通知订阅人
- `discovery.py`：输入 CIDR 网段，多线程 Ping 扫描 + 常见端口探测（22/80/443/161/3306/6379等）粗判设备类型，前端勾选后一键批量导入台账，免去逐台登记

## 6. 已完成并通过校验的工作

- ✅ 全部 Python 文件 `py_compile` 通过
- ✅ `python manage.py makemigrations netmon` 生成迁移成功（未随交付物提供 migrations 文件——**这是刻意的**：spug 项目 `.gitignore` 中排除了所有 `migrations/`，其 `apps/account/management/commands/updatedb.py` 会在部署/更新时自动执行 `makemigrations` + `migrate`，`apps.netmon` 加入 `INSTALLED_APPS` 后会被自动纳入，无需手工处理）
- ✅ `python manage.py check` 对全项目（含新模块）零报错
- ✅ `python manage.py migrate` 成功建表（含与 `account.User`、`host.Host` 的外键关联）
- ✅ 前端页面遵循项目既有规范（mobx `store.js` + antd + bizcharts），未引入 `@antv/data-set` 等新依赖；拓扑图为自实现 SVG 布局，未引入 D3/G6
- ✅ 权限体系：`views.py` 中的 `@auth('netmon.device.view')` 等字符串与 `routes.js` 菜单 `auth`、`system/role/codes.js` 权限目录三方对齐，角色管理页可直接勾选授权

## 7. 集成到你的仓库（3 步）

1. 解压 `spug_netmon_module.zip`，将其中的文件按相同目录结构覆盖/合并到你的 spug 项目根目录（新增文件直接复制，`M` 标记的 6 个文件为对已有文件的增量修改，建议用附带的 `spug_netmon_changes.patch` 通过 `git apply` 应用，冲突处手工核对）：
   ```bash
   cd /path/to/your/spug
   git apply spug_netmon_changes.patch   # 或手工合并 zip 内的文件
   ```
2. 安装新增依赖并初始化数据库：
   ```bash
   cd spug_api
   pip install -r requirements.txt   # 新增 pysnmp，用于 SNMP 采集（可选功能，未装不影响 Ping/Agent方式）
   python manage.py updatedb          # 项目自带命令，会自动为 netmon 生成并应用迁移
   ```
3. 启动新增的 `netmon` 调度进程（与现有 `spug-monitor` 同级，已加入 `docs/docker/spug.ini` 与 `spug_api/tools/supervisor-spug.ini`）：
   ```bash
   supervisorctl update
   supervisorctl start spug-netmon
   ```
   已运行中的 `spug-worker`（`runworker.py`）已被修改为同时消费 `NETMON_WORKER_KEY` 队列，重启该进程即可生效：
   ```bash
   supervisorctl restart spug-worker
   ```
4. 前端：`spug_web` 无新增 npm 依赖，正常 `yarn build` 即可；菜单会在"监控中心"下方新增"IT资源监控"入口（需要角色具备 `netmon.device.view` 权限，管理员可在"系统管理→角色管理"中勾选）。

## 8. 交付清单

- `spug_netmon_module.zip` —— 全部 33 个新增/修改文件（按原仓库目录结构打包，可直接解压覆盖）
- `spug_netmon_changes.patch` —— 对 6 个既有文件的增量修改的标准 git diff，其余为新增文件

## 10. 第二轮增强（易用性 / 可用性 / 自动化 / 报表分析）

在第一轮基础能力之上，针对"帮助管理员更轻松完成监控管理与故障处理、及时应对突发状况"这一目标，新增：

### 10.1 易用性
- 设备批量导入（CSV）+ 批量删除，免去大量资产逐台手工登记/清理
- 设备表单"一键测试连通性"，保存前立即验证 IP/SSH凭据/SNMP团体字是否配置正确，避免配置错误后才在告警里发现
- 总览大屏新增可用率、MTTR、TOP故障设备、异常趋势折线图，一屏掌握"最近是否在变差"

### 10.2 可用性（减少误报、避免漏处理）
- **维护窗口**：计划性变更/停机期间设置维护窗口，期间只采集数据不告警，避免计划内操作产生大量噪音掩盖真正故障
- **告警升级**：`AlertRule` 可配置 `escalate_minutes`，异常长时间未处理会自动二次通知（升级），避免值班遗漏

### 10.3 自动化（故障自愈）
- **RemediationAction**：按设备/分组 + 指标 + 级别匹配，异常触发时自动通过设备关联主机的 SSH 凭据执行处置脚本（如重启服务、清理磁盘），执行结果记录在 `RemediationLog` 并通知，配合冷却时间(`cooldown_minutes`)防止反复触发，直接缩短 MTTR
- `apps.netmon.remediation` 模块与 `apps.netmon.executors` 的采集流水线打通：采集→异常检测→（维护窗口抑制判断）→告警通知→自动化处置，全流程闭环

### 10.4 报表统计分析
- xlsx 报表新增"整体可用率"/"MTTR"汇总行，以及"TOP故障设备"图表页
- `stats.py` 统一了总览大屏与报表的统计口径（MTTR/可用率/趋势/TOP排行），两处数字保持一致

### 10.5 新增前端页面
- 「告警规则」「维护窗口」「自动化处置」三个新 Tab，权限体系复用既有的 `netmon.device.*` 权限，无需额外配置角色权限目录

以上内容已在 `spug-3.0-with-netmon.zip` 中完整合并，可直接部署。

## 11. 后续可选增强（受限于当前环境未实现，建议按需迭代）

- 时序数据长期归档：当前 `MetricRecord` 为自建表，建议数据量增长后接入 Prometheus/InfluxDB
- 拓扑图自动布局：当前为圆形布局，如需自动力导向布局可引入 `@antv/g6` 或 `d3-force`
- 更多通知渠道：当前复用 `apps.notify` 的系统通知，可扩展对接 `alarm.group` 联系组的邮件/短信/webhook
- SNMP v3（加密认证）：当前实现 v1/v2c
- 处置脚本沙箱化/审批流：当前 `RemediationAction` 脚本保存后立即可被自动执行，生产环境建议增加编辑审批与执行白名单机制


