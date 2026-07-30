# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
"""
统计分析
--------
供报表(xlsx)与前端图表共用的统计口径：
  * MTTR（平均故障处理时长，分钟）：resolved_at - created_at 的均值
  * 故障 TOP 排行：区间内异常事件数最多的设备
  * 异常趋势：按天聚合的异常事件数量，用于折线图观察是否有恶化趋势
"""
from datetime import datetime, timedelta
from statistics import mean
from .models import AnomalyEvent, Device


def _parse(dt_str):
    try:
        return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
    except (TypeError, ValueError):
        return None


def compute_mttr(devices, period_start, period_end):
    qs = AnomalyEvent.objects.filter(
        device__in=devices, status='resolved',
        created_at__gte=period_start, created_at__lte=period_end
    ).exclude(resolved_at__isnull=True)
    durations = []
    for e in qs:
        c, r = _parse(e.created_at), _parse(e.resolved_at)
        if c and r and r > c:
            durations.append((r - c).total_seconds() / 60)
    return round(mean(durations), 1) if durations else None


def top_faulty_devices(devices, period_start, period_end, limit=10):
    qs = AnomalyEvent.objects.filter(
        device__in=devices, created_at__gte=period_start, created_at__lte=period_end
    )
    counter = {}
    for e in qs.values_list('device_id', flat=True):
        counter[e] = counter.get(e, 0) + 1
    device_map = {d.id: d for d in devices}
    ranked = sorted(counter.items(), key=lambda x: -x[1])[:limit]
    return [
        {'device_id': did, 'device_name': device_map[did].name, 'device_ip': device_map[did].ip, 'count': cnt}
        for did, cnt in ranked if did in device_map
    ]


def anomaly_trend(devices, days=14):
    """按天统计异常事件数量，返回 [{date, count}]，供前端趋势折线图使用"""
    since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d 00:00:00')
    qs = AnomalyEvent.objects.filter(device__in=devices, created_at__gte=since).values_list('created_at', flat=True)
    buckets = {}
    for created_at in qs:
        day = created_at[:10]
        buckets[day] = buckets.get(day, 0) + 1
    result = []
    for i in range(days, -1, -1):
        day = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        result.append({'date': day, 'count': buckets.get(day, 0)})
    return result


def availability_rate(devices, period_start, period_end):
    """粗粒度可用率估算：1 - (严重异常事件数 / 期间总检测次数的估计)。
    由于本模块未做逐次心跳落库（仅在异常时落异常事件），这里采用工程上常用的近似口径：
    以“未处于 critical/offline 状态的时长占比”估算，简化为基于当前状态快照的即时可用率，
    更精确的SLA统计建议结合 MetricRecord 明细或后续接入专业时序库计算。
    """
    if not devices:
        return None
    healthy = sum(1 for d in devices if d.status in ('online', 'warning', 'unknown'))
    return round(healthy / len(devices) * 100, 2)
