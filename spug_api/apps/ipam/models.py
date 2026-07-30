# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
from django.db import models
from libs import ModelMixin, human_datetime
from apps.account.models import User
from apps.netmon.models import NetGroup, Device
from . import ipcalc
import json


class Subnet(models.Model, ModelMixin):
    """IP 地址池（网段）"""
    name = models.CharField(max_length=100)
    cidr = models.CharField(max_length=50, unique=True, help_text='例如：192.168.10.0/24')
    group = models.ForeignKey(NetGroup, models.SET_NULL, null=True, blank=True)
    vlan_id = models.IntegerField(null=True, blank=True)
    gateway = models.CharField(max_length=50, null=True, blank=True)
    dns_servers = models.CharField(max_length=255, null=True, blank=True)
    warning_threshold = models.IntegerField(default=80, help_text='使用率达到该百分比时触发预警')
    auto_isolate_unauthorized = models.BooleanField(default=False, help_text='发现未授权设备后是否自动尝试隔离')
    desc = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.CharField(max_length=20, default=human_datetime)
    created_by = models.ForeignKey(User, models.PROTECT, related_name='+')

    @property
    def total_count(self):
        return ipcalc.total_usable(self.cidr)

    @property
    def used_count(self):
        return self.addresses.filter(status__in=IPAddress.USED_STATUSES).count()

    def to_view(self):
        tmp = self.to_dict()
        total, used = self.total_count, self.used_count
        tmp['total_count'] = total
        tmp['used_count'] = used
        tmp['free_count'] = max(total - used, 0)
        tmp['usage_rate'] = round(used / total * 100, 1) if total else 0
        tmp['group_name'] = self.group.name if self.group_id else None
        tmp['warning'] = tmp['usage_rate'] >= self.warning_threshold
        return tmp

    def __repr__(self):
        return f'<Subnet {self.cidr}>'

    class Meta:
        db_table = 'ipam_subnets'
        ordering = ('-id',)


class IPAddress(models.Model, ModelMixin):
    """地址状态记录：仅保存"曾经有状态变化"的地址（已分配/预留/冲突/未授权/隔离/已释放），
    未出现的地址在网段范围内即视为空闲，详见 ipcalc.py 顶部说明。
    """
    STATUSES = (
        ('allocated', '已分配'), ('reserved', '预留'), ('released', '已释放'),
        ('conflict', '冲突'), ('unauthorized', '未授权'), ('isolated', '已隔离'),
    )
    USED_STATUSES = ('allocated', 'reserved', 'conflict', 'unauthorized', 'isolated')

    subnet = models.ForeignKey(Subnet, models.CASCADE, related_name='addresses')
    address = models.CharField(max_length=50, db_index=True)
    status = models.CharField(max_length=15, choices=STATUSES, default='allocated')
    mac_address = models.CharField(max_length=20, null=True, blank=True)
    hostname = models.CharField(max_length=100, null=True, blank=True)
    device = models.ForeignKey(Device, models.SET_NULL, null=True, blank=True, related_name='+')
    owner = models.CharField(max_length=100, null=True, blank=True, help_text='使用人/业务方')
    allocated_at = models.CharField(max_length=20, null=True, blank=True)
    expires_at = models.CharField(max_length=20, null=True, blank=True, help_text='租期/预留到期时间，留空表示长期')
    last_seen_at = models.CharField(max_length=20, null=True, blank=True, help_text='最近一次在网段扫描中探测到存活的时间')
    desc = models.CharField(max_length=255, null=True, blank=True)
    updated_at = models.CharField(max_length=20, default=human_datetime)

    def to_view(self):
        tmp = self.to_dict()
        tmp['status_alias'] = self.get_status_display()
        tmp['device_name'] = self.device.name if self.device_id else None
        tmp['subnet_name'] = self.subnet.name if self.subnet_id else None
        tmp['subnet_cidr'] = self.subnet.cidr if self.subnet_id else None
        return tmp

    class Meta:
        db_table = 'ipam_addresses'
        unique_together = ('subnet', 'address')
        ordering = ('address',)


class IPChangeLog(models.Model, ModelMixin):
    """变更审计：完整记录地址生命周期内的每一次变化，供故障排查/合规审计/配置回溯使用"""
    ACTIONS = (
        ('allocate', '分配'), ('release', '释放'), ('reserve', '预留'), ('update', '更新'),
        ('conflict', '发现冲突'), ('unauthorized', '发现未授权设备'), ('isolate', '隔离'), ('restore', '解除隔离'),
    )
    subnet = models.ForeignKey(Subnet, models.CASCADE, related_name='change_logs')
    address = models.CharField(max_length=50, db_index=True)
    action = models.CharField(max_length=15, choices=ACTIONS)
    before = models.TextField(null=True, blank=True, help_text='变更前快照(JSON)')
    after = models.TextField(null=True, blank=True, help_text='变更后快照(JSON)')
    operator = models.ForeignKey(User, models.SET_NULL, null=True, related_name='+', help_text='为空表示系统自动操作')
    remark = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.CharField(max_length=20, default=human_datetime)

    def to_view(self):
        tmp = self.to_dict()
        tmp['action_alias'] = self.get_action_display()
        tmp['operator_name'] = self.operator.nickname if self.operator_id else '系统自动'
        try:
            tmp['before'] = json.loads(self.before) if self.before else None
            tmp['after'] = json.loads(self.after) if self.after else None
        except (TypeError, ValueError):
            pass
        return tmp

    class Meta:
        db_table = 'ipam_change_logs'
        ordering = ('-id',)


class UsageSnapshot(models.Model, ModelMixin):
    """每日用量快照，供预测性洞察做趋势外推（避免直接对历史 IPChangeLog 做重量级聚合计算）"""
    subnet = models.ForeignKey(Subnet, models.CASCADE, related_name='snapshots')
    date = models.CharField(max_length=10, db_index=True)
    used_count = models.IntegerField()
    total_count = models.IntegerField()

    class Meta:
        db_table = 'ipam_usage_snapshots'
        unique_together = ('subnet', 'date')
        ordering = ('-date',)


class IsolationTemplate(models.Model, ModelMixin):
    """隔离处置模板：绑定一台网络设备（网关/防火墙/交换机），通过其 SSH 凭据下发隔离指令，
    脚本内容中可使用 {ip} 占位符。未绑定可执行模板时，隔离操作仅做标记，提示人工现场处置。
    """
    name = models.CharField(max_length=100)
    device = models.ForeignKey(Device, models.CASCADE, related_name='+')
    isolate_script = models.TextField(help_text='隔离时执行的脚本，可用 {ip} 占位符')
    restore_script = models.TextField(null=True, blank=True, help_text='解除隔离时执行的脚本，可用 {ip} 占位符')
    is_default = models.BooleanField(default=False)
    created_at = models.CharField(max_length=20, default=human_datetime)
    created_by = models.ForeignKey(User, models.PROTECT, related_name='+')

    def to_view(self):
        tmp = self.to_dict()
        tmp['device_name'] = self.device.name
        return tmp

    class Meta:
        db_table = 'ipam_isolation_templates'
        ordering = ('-id',)
