# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
#
# apps.ipam —— IP 地址管理（IPAM）
#
#   1. 地址池使用率监控 + 预测性洞察（基于每日用量快照的趋势外推，提前预警耗尽风险）
#      并在网段扫描中自动发现未授权设备、提供隔离处置入口
#   2. 自动化IP分配（在网段内自动挑选下一个可用地址），预防重复占用/人工录入出错
#   3. 完整的变更审计（IPChangeLog）：谁在何时对哪个地址/网段做了什么变更
default_app_config = 'apps.ipam.apps.IpamConfig'
