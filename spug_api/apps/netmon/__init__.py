# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
#
# apps.netmon —— IT 网络与资源一体化监控模块
#
# 本模块在 spug 3.0 现有的“存活探测”（apps.monitor）能力之上，补齐了：
#   1. 网络/主机/应用等 IT 资源的统一台账与拓扑关系（models.Device / Link）
#   2. 指标级实时采集（Ping RTT/丢包、SNMP、Agent(SSH) 采集 CPU/内存/磁盘/网卡流量）
#   3. 时序数据存储、异常检测（静态阈值 + 3-sigma 动态基线）与告警联动
#   4. 拓扑可视化、实时大屏所需的聚合接口
#   5. 报表管理：定时统计报表生成（xlsx，含图表）、自动发现（网段扫描）
default_app_config = 'apps.netmon.apps.NetmonConfig'
