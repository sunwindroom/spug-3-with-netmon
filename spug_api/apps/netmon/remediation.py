# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
"""
故障自动化处置（自愈）
----------------------
当异常事件命中已配置的 RemediationAction（按设备/分组 + 指标 + 级别匹配）时，
自动通过设备关联主机的 SSH 凭据执行处置脚本（如重启服务、清理磁盘等），
执行结果写入 RemediationLog 并通知值班人员，减少人工介入常见故障的时间（MTTR）。
每个动作有冷却时间(cooldown_minutes)，避免同一故障反复触发处置。
"""
from django_redis import get_redis_connection
from apps.notify.models import Notify
from libs.ssh_executor import ssh_exec
from .models import RemediationAction
import logging

LEVEL_RANK = {'info': 0, 'warning': 1, 'critical': 2}
COOLDOWN_KEY = 'spug:netmon:remediation_cooldown:{}:{}'


def _match_actions(device, metric_key, level):
    from django.db.models import Q
    qs = RemediationAction.objects.filter(is_active=True).filter(
        Q(device=device) | Q(device__isnull=True, group__isnull=True) |
        Q(device__isnull=True, group_id=device.group_id)
    )
    matched = []
    for action in qs:
        if action.metric_key and action.metric_key != metric_key:
            continue
        if LEVEL_RANK.get(level, 0) < LEVEL_RANK.get(action.level, 2):
            continue
        matched.append(action)
    return matched


def trigger(device, event):
    """异常事件产生后调用，尝试匹配并执行自动化处置"""
    from .models import RemediationLog  # 延迟导入避免循环依赖
    actions = _match_actions(device, event.metric_key, event.level)
    if not actions:
        return
    if not device.host_id:
        logging.info(f'设备 {device.name} 未关联主机，跳过自动化处置（需要SSH凭据）')
        return

    rds = get_redis_connection()
    for action in actions:
        cd_key = COOLDOWN_KEY.format(action.id, device.id)
        if rds.get(cd_key):
            continue  # 冷却中，跳过
        rds.set(cd_key, '1', ex=action.cooldown_minutes * 60)
        success, output = _execute(device, action.script)
        RemediationLog.objects.create(
            action=action, device=device, anomaly=event, success=success, output=output[:4000]
        )
        try:
            Notify.make_system_notify(
                f'{"自动处置成功" if success else "自动处置失败"}：{device.name} - {action.name}',
                f'触发指标：{event.metric_key}，输出：\n{output[:500]}'
            )
        except Exception as e:
            logging.warning(f'自动处置结果通知发送失败: {e}')


def _execute(device, script):
    exit_code, out = ssh_exec(device.host, script)
    return exit_code == 0, out or ''
