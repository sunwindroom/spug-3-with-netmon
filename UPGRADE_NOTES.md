# 本次改造说明（monitor + netmon 模块统一）

## 一、这次做了什么

你的诉求是"统一所有功能和数据源、删除重复功能、优化前端排版、检查并修复bug"。经过分析，本项目最大的重复功能是并存的两套监控体系：

- **监控中心**（`apps.monitor`，前端菜单 `/monitor`）：站点/端口/进程/自定义脚本/Ping/Docker/数据库/日志共 8 种可用性检测
- **IT资源监控**（`apps.netmon`，前端菜单 `/netmon`）：设备台账 + Ping/SNMP/Agent/HTTP/脚本 5 种指标采集、异常检测、自动化处置、拓扑发现、报表

两者数据模型不同、告警联系组配置分开、前端菜单分开，`netmon` 的仪表盘代码甚至要反向 `import` `monitor` 的内部实现才能拼出总览页——这是本项目里"数据源不统一"的根源。

本次把两者**合并为一套**，统一在 `apps.netmon.models.Device` 模型上，具体见下方"后端变更"。

## 二、后端变更清单

| 文件 | 变更 |
|---|---|
| `apps/netmon/models.py` | `Device.MONITOR_TYPES` 从 5 种扩展到 12 种（新增 http/port/database/ping_check/process/docker/shell/log），新增 `threshold`/`quiet`/`notify_grp`/`notify_mode` 字段承接原监控中心的阈值告警配置 |
| `apps/netmon/checks.py` **(新增)** | 合并原 `monitor/executors.py` 的 8 种可用性检测逻辑，**修复了两个bug**：①`docker_check`/`log_check` 原来调用了未导入的 `ssh_exec`，一使用就报 `NameError`；②`http`类型早就在选项里但从未实现采集分支，选了没反应 |
| `apps/netmon/notify_utils.py` **(新增)** | 合并原 `monitor/utils.py` 的告警通知逻辑（写 Alarm 表 + 多渠道推送），是全系统唯一的告警出口 |
| `apps/netmon/executors.py` | 重写为"指标采集"和"可用性检测"两条流程统一分发 |
| `apps/netmon/scheduler.py` **(新增，原 `apps/monitor/scheduler.py` 迁移合并)** | 统一调度器，只调度 `Device` 表，不再有两套定时任务 |
| `apps/netmon/management/commands/runmonitor.py` | 迁移自 `apps/monitor`，**命令名不变**，你现有的 `tools/start-monitor.sh` 不用改 |
| `apps/netmon/management/commands/migrate_legacy_monitor.py` **(新增)** | 一次性数据迁移命令，见下方"三、部署步骤" |
| `apps/netmon/views.py` | 设备表单支持新字段；`get_overview` 仪表盘改为直接从 `Device` 统计，不再反向依赖 monitor |
| `apps/alarm/views.py`、`apps/exec/views.py`、`apps/home/views.py`、`apps/host/views.py` | 清理对 `apps.monitor` 的引用/权限字符串，改指向统一后的 `netmon.device.*` |
| `apps/monitor/` | **整个目录已删除** |
| `spug/settings.py`、`spug/urls.py` | 移除 `apps.monitor` 的注册和路由 |
| `docs/install.sh` | **修复一个真实 bug**：官方安装脚本写的是 `python manage.py initdb`，但代码里这个命令根本不存在（只有 `updatedb`），照着装第一步就会失败，已改为 `updatedb` |

## 三、部署步骤（内网服务器）

1. 备份好现有数据库（`mysqldump`），这是任何库表结构变更前的标准动作。
2. 用本次的代码整体替换 `spug_api`、`spug_web`、`docs` 目录。
3. 后端：
   ```bash
   cd spug_api
   source venv/bin/activate
   pip install -r requirements.txt
   python manage.py updatedb          # 自动生成并应用本次新增字段的迁移（这是项目原有约定：迁移文件不入库，每次部署自动生成）
   python manage.py migrate_legacy_monitor --dry-run   # 先预览：会把旧"监控中心"的监控项迁移成新的记录
   python manage.py migrate_legacy_monitor             # 确认无误后正式迁移
   ```
   `migrate_legacy_monitor` 是幂等的、只读旧表写新表，**不会删除或修改原 `detections` 表**，迁移完成、确认新版监控中心工作正常后，你可以自行归档/清理旧表。
4. 前端：
   ```bash
   cd spug_web
   npm install    # 或 yarn
   npm run build
   ```
5. 重启服务（`start-api.sh`、`start-worker.sh`、`start-monitor.sh`、`start-ws.sh`，命令名都没变）。
6. 登录后到"监控中心"页面核对迁移过来的监控项（类型、阈值、告警组是否正确），并用页面上的"测试连通性/可用性"按钮抽查几个。

## 四、前端变更清单

- 删除重复的"监控中心"菜单和 `pages/monitor` 整个目录，`pages/netmon` 现在是唯一入口，菜单标题统一为"监控中心"
- 整体菜单重新编排：总览类（工作台/仪表盘）→ 资源与可观测性类（主机管理/IP地址管理/监控中心/报警中心）→ 发布运维类（批量执行/应用发布/任务计划/配置中心）→ 系统管理固定放最后
- "监控中心"的新建/编辑表单补齐了合并进来的 8 种检测类型的录入界面（URL、端口、进程关键字、Docker容器名、日志路径关键字、绑定主机）以及告警阈值/静默期/告警联系组/通知渠道
- 修复了一个会导致仪表盘报错的**遗留bug**：`pages/dashboard/AlarmTrend.js` 原来调用 `/api/monitor/` 接口获取报警趋势的筛选选项，这个接口随 `monitor` 模块删除后会 404，已改为从统一后的 `/api/netmon/device/` 取数据，并修正了筛选参数与后端 `Alarm.type` 字段实际存储值的匹配问题（原代码这里的筛选逻辑其实也是对不上的）
- 设备详情抽屉：对可用性检测类型的监控项不再展示 5 个空的指标趋势图（之前会显示一堆"暂无采集数据"），改为直接展示最近一次检测结果文本

## 五、验证情况说明

我在沙箱环境里用 Python 虚拟环境装了实际依赖，做了以下验证：
- `manage.py check` 全量通过（0 issues）
- 全部 14 个 app 的 `makemigrations` + `migrate` 在全新 SQLite 库上完整建表成功
- 所有新增/改动的 Python 模块逐一 import 测试通过
- 用模拟的旧 `detections` 表数据，完整跑通 `migrate_legacy_monitor` 命令，覆盖 HTTP/端口/进程/日志 4 类典型场景，迁移后字段核对无误
- 对迁移出来的记录跑了一遍 `checks.run_check()`，确认异常情况（网络不通、SSH无密钥等）都被优雅处理、不会抛出未捕获异常
- 前端改动文件用 Babel 做了独立语法检查，全部通过

**没有覆盖到的部分**（沙箱环境限制，需要你在真实环境验证）：
- 没有真实 MySQL/Redis，无法验证在你生产库结构上跑 `updatedb` 的实际效果，建议先在测试库跑一遍
- 没有安装完整前端 `node_modules` 做真实 `npm run build`（只做了 Babel 语法检查），建议部署前本地先 `npm run build` 一遍确认无报错
- 真实的 SNMP/SSH/短信/微信等外部对接没有条件在沙箱里连通测试，建议迁移后对每种类型至少抽查一条真实数据
