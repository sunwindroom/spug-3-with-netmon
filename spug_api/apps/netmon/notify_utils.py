# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
"""
告警通知统一入口
----------------
本模块合并自原 apps.monitor.utils，是"监控中心 + IT资源监控"模块统一后
产生告警通知的唯一入口：统一写入 apps.alarm.models.Alarm（告警历史），
并通过 apps.alarm 配置的联系组 + 多渠道（微信/短信/钉钉/邮件/企业微信/电话/飞书）发送通知。
"""
from django.db import close_old_connections
from apps.alarm.models import Alarm
from libs.spug import Notification
import json


def seconds_to_human(seconds):
    text = ''
    if seconds > 3600:
        text = f'{int(seconds / 3600)}小时'
        seconds = seconds % 3600
    if seconds > 60:
        text += f'{int(seconds / 60)}分钟'
        seconds = seconds % 60
    if seconds:
        text += f'{seconds}秒'
    return text


def _record_alarm(name, type_alias, target, duration, status, notify_grp, notify_mode):
    Alarm.objects.create(
        name=name,
        type=type_alias,
        target=target,
        status=status,
        duration=duration,
        notify_grp=notify_grp,
        notify_mode=notify_mode)


def handle_check_notify(device, target, is_ok, out, fault_times):
    """可用性检测(CHECK_TYPES)专用：按 device.threshold/quiet 判断是否发出故障/恢复通知，
    对应原 monitor.utils.handle_notify，语义完全保持不变。
    """
    close_old_connections()
    duration = seconds_to_human(device.rate * fault_times)
    event = '2' if is_ok else '1'
    type_alias = device.get_monitor_type_display()
    _record_alarm(device.name, type_alias, target, duration, event, device.notify_grp, device.notify_mode)
    grp = json.loads(device.notify_grp) if device.notify_grp else []
    if not grp:
        return
    notify = Notification(grp, event, target, device.name, out, duration)
    notify.dispatch_monitor(json.loads(device.notify_mode) if device.notify_mode else [])


def dispatch_alarm_notify(name, target, message, notify_grp, notify_mode, level='warning'):
    """通用告警通知入口，供指标类监控(AlertRule阈值/动态基线异常)调用，统一走
    alarm 联系组 + 多渠道通知，并写入 Alarm 表使告警历史可追溯。
    """
    close_old_connections()
    grp = json.loads(notify_grp) if isinstance(notify_grp, str) else (notify_grp or [])
    modes = json.loads(notify_mode) if isinstance(notify_mode, str) else (notify_mode or [])
    event = '1'
    Alarm.objects.create(
        name=name,
        type='netmon',
        target=target,
        status=event,
        duration='-',
        notify_grp=json.dumps(grp),
        notify_mode=json.dumps(modes))
    if grp and modes:
        notify = Notification(grp, event, target, name, message, '-')
        notify.dispatch_monitor(modes)
