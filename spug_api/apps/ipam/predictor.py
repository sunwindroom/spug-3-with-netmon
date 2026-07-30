# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
"""
预测性洞察（Predictive Insights）
--------------------------------
基于每日用量快照，用最小二乘法对近 N 天的"已用地址数"做线性趋势外推，
估算按当前增长速率还需多少天耗尽地址池，为资源规划（扩容网段/调整分配策略）提前争取时间。
"""
from datetime import datetime
from .models import Subnet, UsageSnapshot

TREND_WINDOW_DAYS = 14
FORECAST_WARNING_DAYS = 30  # 预计N天内耗尽也纳入预警，即使当前使用率还未达阈值


def take_daily_snapshot():
    """记录所有网段当天的用量快照，供趋势分析使用。建议每天定时执行一次（见 runipam）"""
    today = datetime.now().strftime('%Y-%m-%d')
    for subnet in Subnet.objects.all():
        UsageSnapshot.objects.update_or_create(
            subnet=subnet, date=today,
            defaults={'used_count': subnet.used_count, 'total_count': subnet.total_count}
        )


def _linear_trend(points):
    """最小二乘法拟合 y = a*x + b，points 为 [(x, y), ...]，返回斜率 a（每天增长量）"""
    n = len(points)
    if n < 2:
        return 0
    sum_x = sum(p[0] for p in points)
    sum_y = sum(p[1] for p in points)
    sum_xy = sum(p[0] * p[1] for p in points)
    sum_xx = sum(p[0] * p[0] for p in points)
    denom = n * sum_xx - sum_x * sum_x
    if denom == 0:
        return 0
    return (n * sum_xy - sum_x * sum_y) / denom


def forecast_subnet(subnet):
    """返回该网段的预测性洞察：{usage_rate, daily_growth, days_to_exhaustion, risk_level, message}"""
    snapshots = list(subnet.snapshots.order_by('-date')[:TREND_WINDOW_DAYS])
    snapshots.reverse()
    total = subnet.total_count
    used_now = subnet.used_count
    usage_rate = round(used_now / total * 100, 1) if total else 0

    points = [(i, s.used_count) for i, s in enumerate(snapshots)]
    daily_growth = round(_linear_trend(points), 2) if len(points) >= 3 else None

    days_to_exhaustion = None
    if daily_growth and daily_growth > 0:
        remaining = total - used_now
        days_to_exhaustion = max(int(remaining / daily_growth), 0)

    risk_level = 'low'
    reasons = []
    if usage_rate >= subnet.warning_threshold:
        risk_level = 'high'
        reasons.append(f'当前使用率 {usage_rate}% 已达到预警阈值 {subnet.warning_threshold}%')
    if days_to_exhaustion is not None and days_to_exhaustion <= FORECAST_WARNING_DAYS:
        risk_level = 'high'
        reasons.append(f'按近期增长速率（约每天 {daily_growth} 个地址）预计 {days_to_exhaustion} 天后耗尽')
    elif days_to_exhaustion is not None and days_to_exhaustion <= FORECAST_WARNING_DAYS * 2:
        risk_level = 'medium' if risk_level == 'low' else risk_level
        reasons.append(f'预计约 {days_to_exhaustion} 天后耗尽，建议关注')

    return {
        'subnet_id': subnet.id, 'subnet_name': subnet.name, 'cidr': subnet.cidr,
        'usage_rate': usage_rate, 'used_count': used_now, 'total_count': total,
        'daily_growth': daily_growth, 'days_to_exhaustion': days_to_exhaustion,
        'risk_level': risk_level, 'message': '；'.join(reasons) if reasons else '使用率平稳，暂无耗尽风险',
        'trend': [{'date': s.date, 'used_count': s.used_count} for s in snapshots],
    }


def forecast_all():
    return [forecast_subnet(s) for s in Subnet.objects.all()]
