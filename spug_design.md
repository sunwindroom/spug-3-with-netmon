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

## 12. 第三轮新增：IP地址管理（apps.ipam）

新增独立的 `apps/ipam` 模块（与 `apps/netmon` 平级，通过 `netmon.Device`/`netmon.NetGroup` 关联复用网络设备台账与分组体系），对应需求：

### 12.1 IP使用监控 + 预测性洞察 + 未授权设备检测/隔离协助
- `predictor.py`：每日记录网段用量快照（`UsageSnapshot`），对近14天数据做最小二乘线性趋势外推，估算"按当前增长速率还需多少天耗尽"，与静态阈值预警共同产出 `risk_level`（低/中/高），总览页直接展示每个网段的预测天数与趋势折线图
- `scanner.py`：周期性网段存活扫描（复用Ping方式，不引入新依赖），与IPAM登记记录比对——存活但未登记为已分配/预留 → 判定"未授权设备接入"；已登记但MAC不一致 → 判定"冲突"，两者均写入审计日志并通知
- `isolation.py`：隔离协助——始终先标记地址状态为隔离并留痕；如管理员配置了 `IsolationTemplate`（绑定一台可SSH管理的网关/防火墙/交换机，脚本内容自行编写以适配厂商命令），则自动执行隔离脚本，未配置时明确提示"需人工处置"而不会假装完成了真实网络隔离
- 网段可开启"未授权自动隔离"开关，实现无人值守的初步响应

### 12.2 自动化IP分配
- `allocator.py`：`allocate()` 在不指定地址时自动挑选网段内第一个空闲地址（跳过网关与已占用地址），使用 `select_for_update` 行锁防止并发重复分配；指定地址分配时会校验网段归属与占用状态，从源头预防重复IP
- 地址的"空闲"状态为隐式设计（数据库不预先物化整个网段的地址行，仅保存有状态变化的地址），避免大网段（如 /16）产生数十万行数据，前端「地址分配」页通过 `GET /ipam/subnet/<id>/addresses/` 按需拼出完整地址视图（设有 65536 个地址的展开上限保护）

### 12.3 变更审计历史
- `IPChangeLog` 记录每一次分配/释放/预留/更新/冲突/未授权/隔离/解除隔离，包含变更前后快照（JSON）、操作人（系统自动操作记为空）、备注
- 「变更审计」页支持按网段/地址关键字/操作类型/时间范围筛选查询，点击"查看详情"可展开变更前后的完整字段对比，满足故障排查、合规审计、配置回溯的需要

### 12.4 已完成验证
- ✅ 全部 Python 文件 `py_compile` 通过，`python manage.py check` 全项目零报错
- ✅ 从全新空数据库执行 `python manage.py updatedb`（项目真实的部署初始化命令），15个应用（含 `ipam`）全部迁移成功
- ✅ 通过 Django shell 直接调用 `allocator.allocate/release`、重复分配防护、`predictor.forecast_subnet`、`IPChangeLog` 审计记录，均返回预期结果
- ✅ 通过 `RequestFactory` 对 5 个核心 API 视图（网段列表、自动分配、预测洞察、变更审计、地址视图）做了端到端请求验证，均返回 200 与正确数据结构
- ✅ 新增独立后台进程 `spug-ipam`（`runipam`：每30分钟网段扫描 + 每日0:05用量快照），已加入 `docs/docker/spug.ini` 与 `spug_api/tools/supervisor-spug.ini`
- ✅ 权限目录已加入 `system/role/codes.js`（`ipam.subnet.*`、`ipam.address.*`），前端菜单新增"IP地址管理"入口（`routes.js`）
- 前端 8 个页面同样只做了人工审查，未做浏览器级构建验证，建议部署后 `yarn build` 走查一遍

### 12.5 使用建议
- 隔离脚本涉及真实网络设备变更，建议先在测试环境验证，并考虑为 `IsolationTemplate` 增加审批流程后再启用"未授权自动隔离"
- MAC地址探测依赖 spug 服务器与目标网段处于同一二层网络（ARP可达），跨网段/云环境场景下该字段可能为空，未授权检测仍可基于"存活但未登记"生效，但冲突检测（MAC比对）会退化

## 13. 后续可选增强（受限于当前环境未实现，建议按需迭代）

- 时序数据长期归档：当前 `MetricRecord` 为自建表，建议数据量增长后接入 Prometheus/InfluxDB
- 拓扑图自动布局：当前为圆形布局，如需自动力导向布局可引入 `@antv/g6` 或 `d3-force`
- 更多通知渠道：当前复用 `apps.notify` 的系统通知，可扩展对接 `alarm.group` 联系组的邮件/短信/webhook
- SNMP v3（加密认证）：当前实现 v1/v2c
- 处置脚本沙箱化/审批流：当前 `RemediationAction`/`IsolationTemplate` 脚本保存后立即可被自动执行，生产环境建议增加编辑审批与执行白名单机制
- IPAM 与 DHCP/DNS 系统联动：当前为独立台账，如有 ISC DHCP / Windows DHCP / DNS 服务器，可扩展 `scanner.py` 对接其租约/解析记录做双向核对

## 14. 第四轮：监控中心总览大屏 + 脚本模板库

### 14.1 监控中心总览大屏（参照用户提供的参考图重构）
新增 `pages/monitor/Dashboard.js`，作为"监控中心"页面的默认首屏（原有的任务列表/卡片视图保留为"监控任务"标签页），完全基于真实数据渲染，不展示任何虚构指标：

- **8类监控资源卡片**：站点检测/端口检测/进程检测/自定义脚本/Ping检测/Docker检测/数据库检测/日志监控，每张卡片展示总数、在线数、在线率进度条，配色采用渐变卡片风格
- **性能图表**（复用 `apps.netmon` 采集到的设备指标）：主机流量、时延、CPU/内存/磁盘使用率的最高/平均/最低分组柱状图
- **分布洞察**：内存/CPU使用率区间分布环形图（≥90%/70~90%/40~70%/<40%）、监控资源类型占比、整体在线状态占比
- **资源总量**：CPU核数总量、内存总量、磁盘容量总量（来自 `HostExtend` 云主机元数据，如无云导入主机则为0，如实反映而非虚构）、上下行传输总量（来自netmon实时采集）
- **主机流量排行 TOP10**
- 后端新增 `GET /monitor/dashboard/`（`apps/monitor/views.py` 的 `get_dashboard`），复用既有 `get_overview` 的按目标状态判定逻辑（重构为 `_build_target_status_list()` 公共函数，未改变原有 `/monitor/overview/` 接口的返回结构，不影响现有"监控任务"卡片视图）

### 14.2 监控中心新增3种检测类型
在原有 站点/端口/进程/脚本/Ping 5种基础上，`apps/monitor/models.py` 的 `Detection.TYPES` 新增：
- **Docker检测**：`docker inspect` 判断容器Running状态
- **数据库检测**：对数据库监听端口发起TCP连接判断可达性（不校验账密，前端提供MySQL/MariaDB/Oracle/PostgreSQL/SQLServer/Redis/MongoDB默认端口快捷选择）
- **日志监控**：检测日志文件最近N行内是否出现指定关键字（如ERROR/Exception）

`apps/monitor/executors.py` 相应扩展 `docker_check`/`log_check` 并接入 `dispatch`/`monitor_worker_handler`；`views.py` 的类型校验为动态读取 `Detection.TYPES`，无需额外改动即自动放行新类型；前端 `Step1.js` 相应增加目标/参数输入表单。

### 14.3 脚本模板库（"从模板添加"）
新增管理命令 `python manage.py seed_script_templates`，向执行模板库（`ExecTemplate`，即"配置中心-执行模板"，与监控中心"自定义脚本-从模板添加"共用同一张表）预置 **28 个**开箱即用的监控脚本模板，参考 Zabbix/Nagios 生态的常见检测思路编写，统一约定"异常退出非0，正常退出0"：

| 分类 | 模板数 | 涵盖内容 |
|---|---|---|
| Linux-操作系统 | 6 | CPU/内存/磁盘使用率、系统负载、僵尸进程、SSH登录失败次数 |
| Windows-操作系统 | 5 | CPU/内存/磁盘使用率、Windows服务状态、IIS站点状态（PowerShell，需目标主机安装OpenSSH Server） |
| 容器-Docker | 2 | 容器健康状态、Docker磁盘空间 |
| 数据库-MySQL_MariaDB | 4 | 服务存活(mysqladmin ping)、连接数、主从复制延迟、Galera集群状态 |
| 数据库-Oracle | 2 | 实例状态(OPEN)、表空间使用率 |
| 数据库-PostgreSQL | 1 | 连接数检查 |
| 数据库-Redis | 1 | 连接与内存使用检查 |
| 数据库-MongoDB | 1 | 服务存活检测 |
| 中间件-Nginx | 2 | 进程与配置校验、活跃连接数(stub_status) |
| 中间件-Tomcat | 2 | 进程检查、JVM老年代内存使用率(jstat) |
| 中间件-Apache | 2 | 进程检查(httpd/apache2)、忙碌进程数(mod_status) |

幂等设计：按模板名称去重，重复执行不会覆盖已有模板（含用户自行修改过的内容）。部署后执行一次即可，新建监控任务选择"自定义脚本"→"从模板添加"或"配置中心→执行模板"即可直接看到并使用。

### 14.4 已完成验证
- ✅ 全部新增/修改的 Python 文件 `py_compile` 通过，`python manage.py check` 全项目零报错
- ✅ 从全新空数据库执行 `python manage.py updatedb`，15个应用（含新增的3种监控类型字段变更）全部迁移成功
- ✅ `seed_script_templates` 在全新数据库上执行，成功创建28个模板，二次执行验证幂等（0新建/28跳过）
- ✅ 通过 `RequestFactory` 对 `get_dashboard` 接口做端到端测试，构造了带真实指标数据的 netmon 设备，验证了8类卡片统计、分组柱状图（最高/平均/最低）、使用率区间分布、资源总量、主机流量排行等全部字段计算正确
- ✅ 新增/修改的全部前端文件（`monitor`/`netmon`/`ipam` 三个模块，含 `routes.js`、`codes.js`）通过 `@babel/parser` 语法校验，且逐一核对 `@ant-design/icons`（4.x）与 `bizcharts`（3.5.x）中实际用到的图标与图表组件名称，均已通过安装真实npm包验证存在（排查出并修正了1处不存在的 `DockerOutlined` 图标引用）
- 前端仍未做浏览器级 `yarn build` 与人工点击走查，建议部署后验证一遍界面细节与配色观感

### 14.5 使用建议
- Windows 监控目标需要在目标主机安装并启用 OpenSSH Server（建议将默认Shell设置为PowerShell），这是当前 spug 执行引擎基于SSH的架构约束，不支持WinRM
- 数据库检测为TCP连通性检测（不校验账密），如需更深入的存活判定（如只读查询探测），建议使用"自定义脚本"类型并从模板库选择对应数据库的脚本模板（如 MySQL-服务存活检测 使用了 mysqladmin ping）
- 资源总量卡片中的 CPU核数/内存/磁盘总量依赖 `HostExtend`（云主机导入时自动填充的元数据），手工添加的主机不会计入，如需覆盖手工主机建议后续扩展从 netmon Agent 采集的硬件规格数据




