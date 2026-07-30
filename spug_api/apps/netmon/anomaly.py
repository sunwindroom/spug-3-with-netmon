# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
"""
数据分析与异常检测
------------------
1. 静态阈值：来自 AlertRule 手工配置的规则（大于/小于某值持续N次）
2. 动态基线（3-sigma）：滚动统计近 N 个采样点的均值与标准差，
   当新采样点偏离均值超过 3 倍标准差时判定为异常，无需人工设定阈值，
   适应不同设备、不同指标"没有统一标准"的场景。
"""
from django_redis import get_redis_connection
from statistics import mean, stdev
from datetime import datetime, timedelta
from libs import human_datetime
from .models import MetricRecord, AlertRule, AnomalyEvent, MaintenanceWindow
import json

BASELINE_WINDOW = 50
CONSECUTIVE_KEY = 'spug:netmon:consecutive:{}:{}'  # rule_id, device_id


def _match_operator(value, operator, threshold):
    return {
        '>': value > threshold, '>=': value >= threshold,
        '<': value < threshold, '<=': value <= threshold,
        '==': value == threshold,
    }.get(operator, False)


def check_threshold_rules(device, metric_key, value):
    events = []
    rules = AlertRule.objects.filter(
        is_active=True, metric_key=metric_key
    ).filter(models_q_device_or_group(device))
    rds = get_redis_connection()
    for rule in rules:
        hit = _match_operator(value, rule.operator, rule.threshold)
        counter_key = CONSECUTIVE_KEY.format(rule.id, device.id)
        if hit:
            count = rds.incr(counter_key)
            rds.expire(counter_key, 3600)
            if count >= rule.consecutive_times:
                message = f'{device.name}({device.ip}) 指标[{metric_key}] 当前值 {value} {rule.operator} {rule.threshold}，已连续 {count} 次触发规则「{rule.name}」'
                events.append(AnomalyEvent.objects.create(
                    device=device, metric_key=metric_key, value=value, baseline=rule.threshold,
                    deviation=round(value - rule.threshold, 2), method='threshold',
                    level=rule.level, message=message
                ))
        else:
            rds.delete(counter_key)
    return events


def models_q_device_or_group(device):
    from django.db.models import Q
    q = Q(device=device) | Q(device__isnull=True, group__isnull=True)
    if device.group_id:
        q |= Q(device__isnull=True, group_id=device.group_id)
    return q


def check_dynamic_baseline(device, metric_key, value):
    """3-sigma 动态基线检测，覆盖没有配置静态阈值规则的指标"""
    history = list(
        MetricRecord.objects.filter(device=device, metric_key=metric_key)
        .order_by('-collected_at').values_list('value', flat=True)[:BASELINE_WINDOW]
    )
    if len(history) < 10:
        return None  # 样本不足，暂不做基线判定
    mu, sigma = mean(history), (stdev(history) if len(set(history)) > 1 else 0)
    if sigma == 0:
        return None
    deviation = abs(value - mu) / sigma
    if deviation >= 3:
        level = 'critical' if deviation >= 5 else 'warning'
        message = (
            f'{device.name}({device.ip}) 指标[{metric_key}] 当前值 {value}，'
            f'偏离近期基线(均值 {round(mu, 2)}，标准差 {round(sigma, 2)}) {round(deviation, 1)} 个标准差'
        )
        return AnomalyEvent.objects.create(
            device=device, metric_key=metric_key, value=value, baseline=round(mu, 2),
            deviation=round(deviation, 2), method='3sigma', level=level, message=message
        )
    return None


def in_maintenance(device):
    """是否处于维护窗口内：维护期间只采集数据，不产生异常事件/告警噪音"""
    now = human_datetime()
    windows = MaintenanceWindow.objects.filter(start_at__lte=now, end_at__gte=now)
    return any(w.covers(device) for w in windows)


def analyze(device, metrics: dict):
    """采集完成后调用：写入时序数据 + 触发阈值规则与动态基线检测，返回本次产生的异常事件列表"""
    events = []
    suppressed = in_maintenance(device)
    for metric_key, value in metrics.items():
        MetricRecord.objects.create(device=device, metric_key=metric_key, value=value)
        if suppressed:
            continue
        events.extend(check_threshold_rules(device, metric_key, value))
        baseline_event = check_dynamic_baseline(device, metric_key, value)
        if baseline_event:
            events.append(baseline_event)
    return events


def check_escalations():
    """定期扫描长时间未处理的异常事件，按 AlertRule 配置的 escalate_minutes 升级二次通知。
    由 scheduler.py 中的周期任务调用（默认每分钟一次），无需额外部署新进程。
    """
    from apps.notify.models import Notify
    now = datetime.now()
    open_events = AnomalyEvent.objects.filter(status='open', escalated=False, method='threshold')
    for event in open_events:
        rules = AlertRule.objects.filter(
            metric_key=event.metric_key, is_active=True, escalate_minutes__isnull=False
        )
        for rule in rules:
            try:
                created = datetime.strptime(event.created_at, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                continue
            if now - created >= timedelta(minutes=rule.escalate_minutes):
                event.escalated = True
                event.save(update_fields=['escalated'])
                try:
                    Notify.make_system_notify(
                        f'[升级告警] {event.device.name} 异常持续超过 {rule.escalate_minutes} 分钟未处理',
                        event.message
                    )
                except Exception:
                    pass
                break


def resolve_device_status(device, metrics, events):
    """根据本轮采集结果与异常事件更新设备健康状态，供拓扑图/总览大屏着色使用"""
    if events:
        level = 'critical' if any(e.level == 'critical' for e in events) else 'warning'
        device.status = level
    else:
        device.status = 'online'
    device.last_value = json.dumps(metrics)
    device.latest_check_at = human_datetime()
    device.save(update_fields=['status', 'latest_check_at', 'last_value'])
