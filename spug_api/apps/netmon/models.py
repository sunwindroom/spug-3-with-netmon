# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
from django.db import models
from libs import ModelMixin, human_datetime
from apps.account.models import User
from apps.host.models import Host, Group
import json



class Device(models.Model, ModelMixin):
    """统一 IT 资源台账：服务器/网络设备/存储/中间件/应用等"""
    CATEGORIES = (
        ('server', '服务器'),
        ('switch', '交换机'),
        ('router', '路由器'),
        ('firewall', '防火墙'),
        ('load_balancer', '负载均衡'),
        ('storage', '存储设备'),
        ('database', '数据库'),
        ('middleware', '中间件'),
        ('application', '业务应用'),
        ('other', '其他'),
    )
    # 指标采集类（写入 MetricRecord，走 AlertRule / 动态基线异常检测）
    METRIC_TYPES = (
        ('ping', 'Ping探测(指标采集)'),
        ('snmp', 'SNMP采集'),
        ('agent', 'Agent(SSH)采集'),
        ('script', '自定义采集脚本(数值)'),
    )
    # 可用性检测类（原 monitor.Detection 迁移而来，走 threshold/quiet 阈值告警）
    CHECK_TYPES = (
        ('http', 'HTTP/站点检测'),
        ('port', '端口检测'),
        ('database', '数据库端口检测'),
        ('ping_check', 'Ping可用性检测(阈值告警)'),
        ('process', '进程检测'),
        ('docker', 'Docker容器检测'),
        ('shell', '命令检测(退出码)'),
        ('log', '日志关键字监控'),
    )
    MONITOR_TYPES = METRIC_TYPES + CHECK_TYPES
    STATUSES = (
        ('unknown', '未知'),
        ('online', '正常'),
        ('warning', '告警'),
        ('critical', '严重'),
        ('offline', '离线'),
    )

    name = models.CharField(max_length=100)
    ip = models.CharField(max_length=50, db_index=True)
    category = models.CharField(max_length=20, choices=CATEGORIES, default='server')
    group = models.ForeignKey(Group, models.SET_NULL, null=True, blank=True, related_name='netmon_devices')
    vendor = models.CharField(max_length=50, null=True, blank=True)
    model_name = models.CharField(max_length=50, null=True, blank=True)
    location = models.CharField(max_length=100, null=True, blank=True)

    monitor_type = models.CharField(max_length=10, choices=MONITOR_TYPES, default='ping')
    host = models.ForeignKey(Host, models.SET_NULL, null=True, blank=True, related_name='+')
    snmp_version = models.CharField(max_length=5, default='2c')
    snmp_community = models.CharField(max_length=50, default='public')
    snmp_port = models.IntegerField(default=161)
    extra = models.TextField(null=True, blank=True, help_text='采集脚本内容，或可用性检测的参数(JSON)，含义随monitor_type而定')

    rate = models.IntegerField(default=60, help_text='采集/检测周期(秒)')
    status = models.CharField(max_length=10, choices=STATUSES, default='unknown')
    last_value = models.TextField(null=True, blank=True, help_text='最近一次采集到的指标快照(JSON)')
    latest_check_at = models.CharField(max_length=20, null=True)
    is_active = models.BooleanField(default=True)
    desc = models.CharField(max_length=255, null=True, blank=True)

    # ---- 可用性检测(CHECK_TYPES)专用告警参数：由原 monitor.Detection 合并而来 ----
    threshold = models.IntegerField(default=3, help_text='连续失败多少次后判定为故障并发出告警(仅可用性检测类型)')
    quiet = models.IntegerField(default=24 * 60, help_text='同一故障的告警静默期(分钟)，避免重复刷屏(仅可用性检测类型)')
    notify_grp = models.CharField(max_length=255, default='[]', help_text='告警联系组id列表(JSON，仅可用性检测类型)')
    notify_mode = models.CharField(max_length=255, default='[]', help_text='告警方式列表(JSON，仅可用性检测类型)')

    created_at = models.CharField(max_length=20, default=human_datetime)
    created_by = models.ForeignKey(User, models.PROTECT, related_name='+')

    def is_check_type(self):
        return self.monitor_type in dict(self.CHECK_TYPES)

    def to_view(self):
        tmp = self.to_dict()
        tmp['category_alias'] = self.get_category_display()
        tmp['monitor_type_alias'] = self.get_monitor_type_display()
        tmp['status_alias'] = self.get_status_display()
        tmp['group_name'] = self.group.name if self.group_id else None
        tmp['is_check_type'] = self.is_check_type()
        try:
            tmp['last_value'] = json.loads(self.last_value) if self.last_value else {}
        except (TypeError, ValueError):
            tmp['last_value'] = {}
        try:
            tmp['notify_grp'] = json.loads(self.notify_grp) if self.notify_grp else []
        except (TypeError, ValueError):
            tmp['notify_grp'] = []
        try:
            tmp['notify_mode'] = json.loads(self.notify_mode) if self.notify_mode else []
        except (TypeError, ValueError):
            tmp['notify_mode'] = []
        return tmp

    def __repr__(self):
        return '<Device %r(%s)>' % (self.name, self.ip)

    class Meta:
        db_table = 'netmon_devices'
        ordering = ('-id',)


class Link(models.Model, ModelMixin):
    """拓扑连线：设备间的物理/逻辑连接关系"""
    LINK_TYPES = (('physical', '物理链路'), ('logical', '逻辑链路'))

    source = models.ForeignKey(Device, models.CASCADE, related_name='links_out')
    target = models.ForeignKey(Device, models.CASCADE, related_name='links_in')
    link_type = models.CharField(max_length=10, choices=LINK_TYPES, default='physical')
    bandwidth_mbps = models.IntegerField(null=True, blank=True)
    desc = models.CharField(max_length=255, null=True, blank=True)

    def to_view(self):
        return dict(
            id=self.id, source=self.source_id, target=self.target_id,
            link_type=self.link_type, bandwidth_mbps=self.bandwidth_mbps, desc=self.desc
        )

    class Meta:
        db_table = 'netmon_links'


class MetricRecord(models.Model, ModelMixin):
    """指标时序数据（轻量内置实现；生产环境建议对接 Prometheus/InfluxDB 做长周期存储）"""
    METRIC_KEYS = (
        ('rtt', '时延(ms)'), ('loss', '丢包率(%)'),
        ('cpu', 'CPU使用率(%)'), ('memory', '内存使用率(%)'), ('disk', '磁盘使用率(%)'),
        ('net_in', '入流量(Kbps)'), ('net_out', '出流量(Kbps)'),
    )
    device = models.ForeignKey(Device, models.CASCADE, related_name='metrics')
    metric_key = models.CharField(max_length=20, choices=METRIC_KEYS)
    value = models.FloatField()
    unit = models.CharField(max_length=10, null=True, blank=True)
    collected_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'netmon_metric_records'
        indexes = [models.Index(fields=['device', 'metric_key', 'collected_at'])]
        ordering = ('-collected_at',)


class AlertRule(models.Model, ModelMixin):
    """指标阈值告警规则"""
    OPERATORS = (('>', '大于'), ('>=', '大于等于'), ('<', '小于'), ('<=', '小于等于'), ('==', '等于'))
    LEVELS = (('info', '提示'), ('warning', '告警'), ('critical', '严重'))

    name = models.CharField(max_length=50)
    group = models.ForeignKey(Group, models.SET_NULL, null=True, blank=True)
    device = models.ForeignKey(Device, models.CASCADE, null=True, blank=True, related_name='alert_rules')
    metric_key = models.CharField(max_length=20)
    operator = models.CharField(max_length=2, choices=OPERATORS)
    threshold = models.FloatField()
    consecutive_times = models.IntegerField(default=1)
    level = models.CharField(max_length=10, choices=LEVELS, default='warning')
    notify_grp = models.CharField(max_length=255, default='[]')
    notify_mode = models.CharField(max_length=255, default='[]')
    escalate_minutes = models.IntegerField(null=True, blank=True, help_text='未处理超过N分钟后升级通知，留空表示不升级')
    escalate_notify_grp = models.CharField(max_length=255, default='[]')
    is_active = models.BooleanField(default=True)
    created_at = models.CharField(max_length=20, default=human_datetime)
    created_by = models.ForeignKey(User, models.PROTECT, related_name='+')

    def to_view(self):
        tmp = self.to_dict()
        tmp['notify_grp'] = json.loads(self.notify_grp)
        tmp['notify_mode'] = json.loads(self.notify_mode)
        tmp['escalate_notify_grp'] = json.loads(self.escalate_notify_grp)
        return tmp

    class Meta:
        db_table = 'netmon_alert_rules'
        ordering = ('-id',)


class AnomalyEvent(models.Model, ModelMixin):
    """异常/告警事件记录（阈值型 + 统计学动态基线型）"""
    METHODS = (('threshold', '静态阈值'), ('3sigma', '3-sigma动态基线'), ('ewma', 'EWMA平滑基线'))
    LEVELS = (('info', '提示'), ('warning', '告警'), ('critical', '严重'))
    STATUSES = (('open', '未处理'), ('acknowledged', '已确认'), ('resolved', '已恢复'))

    device = models.ForeignKey(Device, models.CASCADE, related_name='anomalies')
    metric_key = models.CharField(max_length=20)
    value = models.FloatField()
    baseline = models.FloatField(null=True)
    deviation = models.FloatField(null=True)
    method = models.CharField(max_length=10, choices=METHODS, default='threshold')
    level = models.CharField(max_length=10, choices=LEVELS, default='warning')
    message = models.CharField(max_length=255)
    status = models.CharField(max_length=15, choices=STATUSES, default='open')
    escalated = models.BooleanField(default=False)
    created_at = models.CharField(max_length=20, default=human_datetime)
    resolved_at = models.CharField(max_length=20, null=True)

    def to_view(self):
        tmp = self.to_dict()
        tmp['device_name'] = self.device.name
        tmp['device_ip'] = self.device.ip
        tmp['level_alias'] = self.get_level_display()
        tmp['status_alias'] = self.get_status_display()
        return tmp

    class Meta:
        db_table = 'netmon_anomaly_events'
        ordering = ('-id',)


class MaintenanceWindow(models.Model, ModelMixin):
    """维护窗口：计划性停机/变更期间抑制误报，避免刷屏告警影响真正故障的排查"""
    name = models.CharField(max_length=100)
    group = models.ForeignKey(Group, models.SET_NULL, null=True, blank=True)
    device = models.ForeignKey(Device, models.CASCADE, null=True, blank=True, related_name='maintenance_windows')
    start_at = models.CharField(max_length=20)
    end_at = models.CharField(max_length=20)
    reason = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.CharField(max_length=20, default=human_datetime)
    created_by = models.ForeignKey(User, models.PROTECT, related_name='+')

    def covers(self, device):
        now = human_datetime()
        if not (self.start_at <= now <= self.end_at):
            return False
        if self.device_id:
            return self.device_id == device.id
        if self.group_id:
            return self.group_id == device.group_id
        return True  # 未指定设备/分组表示全局维护窗口

    def to_view(self):
        tmp = self.to_dict()
        tmp['device_name'] = self.device.name if self.device_id else None
        tmp['group_name'] = self.group.name if self.group_id else None
        tmp['is_active'] = self.start_at <= human_datetime() <= self.end_at
        return tmp

    class Meta:
        db_table = 'netmon_maintenance_windows'
        ordering = ('-id',)


class RemediationAction(models.Model, ModelMixin):
    """故障自愈/自动化处置动作：命中规则后自动通过 SSH 在目标主机上执行处置脚本
    （例如重启服务、清理磁盘、拉起进程），执行结果记录在 RemediationLog，
    减少值班人员对常见故障的重复手工操作，提升故障处理时效（MTTR）。
    """
    name = models.CharField(max_length=100)
    device = models.ForeignKey(Device, models.CASCADE, null=True, blank=True, related_name='remediation_actions')
    group = models.ForeignKey(Group, models.SET_NULL, null=True, blank=True)
    metric_key = models.CharField(max_length=20, null=True, blank=True, help_text='为空表示任意指标异常均可触发')
    level = models.CharField(max_length=10, default='critical', help_text='达到该级别及以上才触发自动处置')
    script = models.TextField(help_text='将通过设备关联主机的SSH凭据执行的shell脚本')
    cooldown_minutes = models.IntegerField(default=15, help_text='同一设备两次自动处置的最小间隔，避免反复执行')
    is_active = models.BooleanField(default=True)
    created_at = models.CharField(max_length=20, default=human_datetime)
    created_by = models.ForeignKey(User, models.PROTECT, related_name='+')

    def to_view(self):
        tmp = self.to_dict()
        tmp['device_name'] = self.device.name if self.device_id else None
        tmp['group_name'] = self.group.name if self.group_id else None
        return tmp

    class Meta:
        db_table = 'netmon_remediation_actions'
        ordering = ('-id',)


class RemediationLog(models.Model, ModelMixin):
    """自动化处置执行记录，供故障复盘与审计"""
    action = models.ForeignKey(RemediationAction, models.CASCADE, related_name='logs')
    device = models.ForeignKey(Device, models.CASCADE, related_name='remediation_logs')
    anomaly = models.ForeignKey(AnomalyEvent, models.SET_NULL, null=True, related_name='remediation_logs')
    success = models.BooleanField(default=False)
    output = models.TextField(null=True, blank=True)
    created_at = models.CharField(max_length=20, default=human_datetime)

    def to_view(self):
        tmp = self.to_dict()
        tmp['action_name'] = self.action.name
        tmp['device_name'] = self.device.name
        return tmp

    class Meta:
        db_table = 'netmon_remediation_logs'
        ordering = ('-id',)


class Report(models.Model, ModelMixin):
    """报表定义：统计范围、周期、格式与订阅人"""
    REPORT_TYPES = (('daily', '日报'), ('weekly', '周报'), ('monthly', '月报'), ('manual', '手动/自定义'))

    name = models.CharField(max_length=100)
    report_type = models.CharField(max_length=10, choices=REPORT_TYPES, default='daily')
    group = models.ForeignKey(Group, models.SET_NULL, null=True, blank=True, help_text='为空表示统计全部资源')
    recipients = models.CharField(max_length=255, default='[]', help_text='通知联系组id列表(JSON)')
    is_active = models.BooleanField(default=True)
    last_generated_at = models.CharField(max_length=20, null=True)
    created_at = models.CharField(max_length=20, default=human_datetime)
    created_by = models.ForeignKey(User, models.PROTECT, related_name='+')

    def to_view(self):
        tmp = self.to_dict()
        tmp['report_type_alias'] = self.get_report_type_display()
        tmp['recipients'] = json.loads(self.recipients)
        tmp['group_name'] = self.group.name if self.group_id else '全部资源'
        return tmp

    class Meta:
        db_table = 'netmon_reports'
        ordering = ('-id',)


class ReportRecord(models.Model, ModelMixin):
    """报表生成历史"""
    report = models.ForeignKey(Report, models.CASCADE, related_name='records')
    period_start = models.CharField(max_length=20)
    period_end = models.CharField(max_length=20)
    file_path = models.CharField(max_length=255)
    summary = models.TextField(default='{}')
    created_at = models.CharField(max_length=20, default=human_datetime)

    def to_view(self):
        tmp = self.to_dict()
        tmp['report_name'] = self.report.name
        try:
            tmp['summary'] = json.loads(self.summary)
        except (TypeError, ValueError):
            tmp['summary'] = {}
        return tmp

    class Meta:
        db_table = 'netmon_report_records'
        ordering = ('-id',)
