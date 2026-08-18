# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
from django.views.generic import View
from django.conf import settings
from django.db.models import Count
from django_redis import get_redis_connection
from libs import json_response, JsonParser, Argument, human_datetime, auth
from apps.netmon.models import (
    Device, Link, MetricRecord, AlertRule, AnomalyEvent, Report, ReportRecord,
    MaintenanceWindow, RemediationAction, RemediationLog, ConfigBackup
)

from apps.netmon import discovery, reports as report_builder, stats as stats_builder, collectors, checks
from apps.setting.utils import AppSetting
from threading import Thread
from datetime import datetime, timedelta
from statistics import mean
import json
import uuid
import os
import subprocess
import csv
import io

NETMON_KEY = settings.NETMON_KEY



# ------------------------------------------------------------------ 设备台账 -----
class DeviceView(View):
    @auth('netmon.device.view')
    def get(self, request):
        group_id = request.GET.get('group_id')
        qs = Device.objects.all()
        if group_id:
            qs = qs.filter(group_id=group_id)
        return json_response([x.to_view() for x in qs])

    @auth('netmon.device.add|netmon.device.edit')
    def post(self, request):
        form, error = JsonParser(
            Argument('id', type=int, required=False),
            Argument('name', help='请输入设备名称'),
            Argument('ip', help='请输入IP地址'),
            Argument('category', default='server'),
            Argument('group_id', type=int, required=False),
            Argument('vendor', required=False),
            Argument('model_name', required=False),
            Argument('location', required=False),
            Argument('monitor_type', default='ping'),
            Argument('host_id', type=int, required=False),
            Argument('snmp_version', default='2c'),
            Argument('snmp_community', default='public'),
            Argument('snmp_port', type=int, default=161),
            Argument('extra', required=False),
            Argument('rate', type=int, default=60),
            Argument('desc', required=False),
            Argument('threshold', type=int, default=3),
            Argument('quiet', type=int, default=24 * 60),
            Argument('notify_grp', type=list, default=[]),
            Argument('notify_mode', type=list, default=[]),
        ).parse(request.body)
        if error is None:
            if set(form.notify_mode).intersection(['1', '2', '6']):
                if not AppSetting.get_default('spug_push_key'):
                    return json_response(error='报警方式微信、短信、电话需要配置推送服务（系统设置/推送服务设置），请配置后再启用该报警方式。')
            form.notify_grp = json.dumps(form.notify_grp)
            form.notify_mode = json.dumps(form.notify_mode)
            device_id = form.pop('id', None)
            rds_cli = get_redis_connection()
            if device_id:
                Device.objects.filter(pk=device_id).update(**form)
            else:
                device = Device.objects.create(created_by=request.user, **form)
                device_id = device.id
            rds_cli.lpush(NETMON_KEY, json.dumps({'action': 'modify', 'id': device_id, 'rate': form.rate}))
        return json_response(error=error)

    @auth('netmon.device.edit')
    def patch(self, request):
        form, error = JsonParser(
            Argument('id', type=int, help='请指定操作对象'),
            Argument('is_active', type=bool, required=False),
        ).parse(request.body, True)
        if error is None:
            Device.objects.filter(pk=form.id).update(**form)
            device = Device.objects.filter(pk=form.id).first()
            rds_cli = get_redis_connection()
            if device and device.is_active:
                rds_cli.lpush(NETMON_KEY, json.dumps({'action': 'modify', 'id': device.id, 'rate': device.rate}))
            else:
                rds_cli.lpush(NETMON_KEY, json.dumps({'action': 'remove', 'id': form.id}))
        return json_response(error=error)

    @auth('netmon.device.del')
    def delete(self, request):
        form, error = JsonParser(Argument('id', type=int, help='请指定操作对象')).parse(request.GET)
        if error is None:
            Device.objects.filter(pk=form.id).delete()
            rds_cli = get_redis_connection()
            rds_cli.lpush(NETMON_KEY, json.dumps({'action': 'remove', 'id': form.id}))
        return json_response(error=error)


@auth('netmon.device.del')
def batch_delete_devices(request):
    form, error = JsonParser(Argument('ids', type=list, help='请选择要删除的设备')).parse(request.body)
    if error:
        return json_response(error=error)
    rds_cli = get_redis_connection()
    count = Device.objects.filter(pk__in=form.ids).count()
    Device.objects.filter(pk__in=form.ids).delete()
    for device_id in form.ids:
        rds_cli.lpush(NETMON_KEY, json.dumps({'action': 'remove', 'id': device_id}))
    return json_response({'deleted': count})


@auth('netmon.device.add')
def import_devices_csv(request):
    """批量导入设备：CSV 表头 name,ip,category,monitor_type,group_id（后三列可留空使用默认值），
    便于管理员从 Excel/其它CMDB系统导出的资产清单快速批量录入，避免逐台手工创建。
    """
    file = request.FILES.get('file')
    if not file:
        return json_response(error='请上传CSV文件')
    try:
        text = file.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        text = file.read().decode('gbk', errors='ignore')
    reader = csv.DictReader(io.StringIO(text))
    created, skipped, errors = 0, 0, []
    valid_categories = {c for c, _ in Device.CATEGORIES}
    for i, row in enumerate(reader, 2):
        name, ip = (row.get('name') or '').strip(), (row.get('ip') or '').strip()
        if not name or not ip:
            errors.append(f'第{i}行：name/ip 不能为空')
            continue
        if Device.objects.filter(ip=ip).exists():
            skipped += 1
            continue
        category = row.get('category', 'server').strip() or 'server'
        if category not in valid_categories:
            category = 'other'
        Device.objects.create(
            name=name, ip=ip, category=category,
            monitor_type=row.get('monitor_type', 'ping').strip() or 'ping',
            group_id=row.get('group_id') or None,
            created_by=request.user,
        )
        created += 1
    return json_response({'created': created, 'skipped': skipped, 'errors': errors})


@auth('netmon.device.view')
def test_connectivity(request):
    """新建/编辑设备时"一键测试连通性"：立即执行一次采集，便于快速验证IP/凭据/SNMP团体字是否配置正确"""
    form, error = JsonParser(
        Argument('id', type=int, required=False),
        Argument('ip', help='请输入IP地址'),
        Argument('monitor_type', default='ping'),
        Argument('snmp_community', default='public'),
        Argument('snmp_port', type=int, default=161),
        Argument('host_id', type=int, required=False),
        Argument('extra', required=False),
    ).parse(request.body)
    if error:
        return json_response(error=error)
    if form.id:
        device = Device.objects.filter(pk=form.id).first()
    else:
        device = Device(
            ip=form.ip, monitor_type=form.monitor_type, snmp_community=form.snmp_community,
            snmp_port=form.snmp_port, host_id=form.host_id, extra=form.extra
        )
    if not device:
        return json_response(error='设备不存在')
    if device.is_check_type():
        try:
            is_ok, message = checks.run_check(device)
        except Exception as e:
            return json_response({'success': False, 'message': str(e)})
        return json_response({'success': is_ok, 'message': message})
    try:
        result = collectors.collect(device)
    except Exception as e:
        return json_response({'success': False, 'message': str(e)})
    if result is None:
        return json_response({'success': False, 'message': '未采集到任何数据，请检查IP可达性/凭据/SNMP配置'})
    return json_response({'success': True, 'metrics': result})


# ------------------------------------------------------------------ 拓扑 -----
class TopologyView(View):
    @auth('netmon.device.view')
    def get(self, request):
        group_id = request.GET.get('group_id')
        devices = Device.objects.all()
        if group_id:
            devices = devices.filter(group_id=group_id)
        device_ids = list(devices.values_list('id', flat=True))
        links = Link.objects.filter(source_id__in=device_ids, target_id__in=device_ids)
        nodes = [{
            'id': d.id, 'name': d.name, 'ip': d.ip, 'category': d.category,
            'status': d.status, 'monitor_type': d.monitor_type,
        } for d in devices]
        edges = [x.to_view() for x in links]
        return json_response({'nodes': nodes, 'edges': edges})

    @auth('netmon.device.edit')
    def post(self, request):
        form, error = JsonParser(
            Argument('source', type=int, help='请选择起始设备'),
            Argument('target', type=int, help='请选择目标设备'),
            Argument('link_type', default='physical'),
            Argument('bandwidth_mbps', type=int, required=False),
            Argument('desc', required=False),
        ).parse(request.body)
        if error is None:
            Link.objects.create(source_id=form.source, target_id=form.target, link_type=form.link_type,
                                 bandwidth_mbps=form.bandwidth_mbps, desc=form.desc)
        return json_response(error=error)

    @auth('netmon.device.edit')
    def delete(self, request):
        form, error = JsonParser(Argument('id', type=int, help='请指定操作对象')).parse(request.GET)
        if error is None:
            Link.objects.filter(pk=form.id).delete()
        return json_response(error=error)


def _metric_stats(devices, key):
    values = []
    for d in devices:
        try:
            v = json.loads(d.last_value) if d.last_value else {}
        except (TypeError, ValueError):
            v = {}
        if key in v:
            values.append(v[key])
    if not values:
        return {'max': 0, 'avg': 0, 'min': 0}
    return {'max': round(max(values), 1), 'avg': round(mean(values), 1), 'min': round(min(values), 1)}


def _distribution(devices, key):
    buckets = {'≥90%': 0, '70%~90%': 0, '40%~70%': 0, '<40%': 0}
    for d in devices:
        try:
            v = json.loads(d.last_value) if d.last_value else {}
        except (TypeError, ValueError):
            v = {}
        val = v.get(key)
        if val is None:
            continue
        if val >= 90:
            buckets['≥90%'] += 1
        elif val >= 70:
            buckets['70%~90%'] += 1
        elif val >= 40:
            buckets['40%~70%'] += 1
        else:
            buckets['<40%'] += 1
    return [{'range': k, 'count': v} for k, v in buckets.items()]


# ------------------------------------------------------------------ 实时总览大屏 -----
@auth('netmon.device.view')
def get_overview(request):
    from apps.host.models import HostExtend
    from apps.alarm.models import Alarm

    devices = Device.objects.all()
    status_counts = {'online': 0, 'warning': 0, 'critical': 0, 'offline': 0, 'unknown': 0}
    category_counts = {}
    for d in devices:
        status_counts[d.status] = status_counts.get(d.status, 0) + 1
        category_counts[d.category] = category_counts.get(d.category, 0) + 1

    recent_since = (datetime.now() - timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S')
    top_anomalies = AnomalyEvent.objects.filter(
        status='open', created_at__gte=recent_since
    ).order_by('-id')[:10]

    cpu_avg = MetricRecord.objects.filter(
        metric_key='cpu', collected_at__gte=datetime.now() - timedelta(minutes=10)
    ).values_list('value', flat=True)
    mem_avg = MetricRecord.objects.filter(
        metric_key='memory', collected_at__gte=datetime.now() - timedelta(minutes=10)
    ).values_list('value', flat=True)

    since_7d = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
    now_str = human_datetime()
    all_devices = list(devices)
    mttr = stats_builder.compute_mttr(all_devices, since_7d, now_str)
    avail = stats_builder.availability_rate(all_devices, since_7d, now_str)
    trend = stats_builder.anomaly_trend(all_devices, days=14)
    top_faulty = stats_builder.top_faulty_devices(all_devices, since_7d, now_str, limit=5)

    # ---- 可用性检测类设备（原 monitor 模块的检测能力，现已统一到 Device 模型）的在线率统计 ----
    check_devices = [d for d in all_devices if d.is_check_type()]
    type_stats = []
    for code, alias in Device.CHECK_TYPES:
        items = [d for d in check_devices if d.monitor_type == code]
        total = len(items)
        online = len([d for d in items if d.status not in ('critical', 'offline')])
        type_stats.append({
            'type': code, 'type_alias': alias, 'total': total, 'online': online,
            'rate': round(online / total * 100, 1) if total else 0.0,
        })

    since_1h = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
    recent_alerts_1h = Alarm.objects.filter(status='1', created_at__gte=since_1h).count()

    dev_list = all_devices
    bar_charts = {
        'traffic': [
            {'metric': '主机上行流量(Kb/s)', **_metric_stats(dev_list, 'net_out')},
            {'metric': '主机下行流量(Kb/s)', **_metric_stats(dev_list, 'net_in')},
        ],
        'load': [
            {'metric': '主机时延(ms)', **_metric_stats(dev_list, 'rtt')},
        ],
        'usage': [
            {'metric': '主机CPU使用率(%)', **_metric_stats(dev_list, 'cpu')},
            {'metric': '主机内存使用率(%)', **_metric_stats(dev_list, 'memory')},
            {'metric': '磁盘使用率(%)', **_metric_stats(dev_list, 'disk')},
        ],
    }

    resource_totals = {'cpu_cores': 0, 'memory_gb': 0, 'disk_gb': 0, 'traffic_in_kbps': 0, 'traffic_out_kbps': 0}
    for ext in HostExtend.objects.all():
        resource_totals['cpu_cores'] += ext.cpu or 0
        resource_totals['memory_gb'] += ext.memory or 0
        try:
            disks = json.loads(ext.disk) if ext.disk else []
            resource_totals['disk_gb'] += sum(x.get('size', 0) for x in disks if isinstance(x, dict))
        except (TypeError, ValueError):
            pass
    for d in dev_list:
        try:
            v = json.loads(d.last_value) if d.last_value else {}
        except (TypeError, ValueError):
            v = {}
        resource_totals['traffic_in_kbps'] += v.get('net_in', 0)
        resource_totals['traffic_out_kbps'] += v.get('net_out', 0)
    resource_totals = {k: round(v, 1) for k, v in resource_totals.items()}

    host_traffic = []
    for d in dev_list:
        try:
            v = json.loads(d.last_value) if d.last_value else {}
        except (TypeError, ValueError):
            v = {}
        total_traffic = (v.get('net_in', 0) or 0) + (v.get('net_out', 0) or 0)
        if total_traffic > 0:
            host_traffic.append({'name': d.name, 'ip': d.ip, 'value': round(total_traffic, 1)})
    host_traffic.sort(key=lambda x: -x['value'])

    return json_response({
        'device_total': devices.count(),
        'status_counts': status_counts,
        'category_counts': category_counts,
        'fleet_cpu_avg': round(mean(cpu_avg), 2) if cpu_avg else None,
        'fleet_mem_avg': round(mean(mem_avg), 2) if mem_avg else None,
        'top_anomalies': [x.to_view() for x in top_anomalies],
        'mttr_minutes': mttr,
        'availability_rate': avail,
        'anomaly_trend': trend,
        'top_faulty_7d': top_faulty,
        'type_stats': type_stats,
        'recent_alerts_1h': recent_alerts_1h,
        'resource_total_count': devices.count(),
        'bar_charts': bar_charts,
        'memory_distribution': _distribution(dev_list, 'memory'),
        'cpu_distribution': _distribution(dev_list, 'cpu'),
        'resource_totals': resource_totals,
        'host_traffic': host_traffic[:10],
    })


# ------------------------------------------------------------------ 历史指标查询 -----
@auth('netmon.device.view')
def get_metric_history(request):
    form, error = JsonParser(
        Argument('device_id', type=int, help='请指定设备'),
        Argument('metric_key', help='请指定指标'),
        Argument('minutes', type=int, default=60),
    ).parse(request.GET)
    if error:
        return json_response(error=error)
    since = datetime.now() - timedelta(minutes=form.minutes)
    records = MetricRecord.objects.filter(
        device_id=form.device_id, metric_key=form.metric_key, collected_at__gte=since
    ).order_by('collected_at')
    return json_response([
        {'time': x.collected_at.strftime('%Y-%m-%d %H:%M:%S'), 'value': x.value} for x in records
    ])


# ------------------------------------------------------------------ 异常事件 -----
class AnomalyView(View):
    @auth('netmon.device.view')
    def get(self, request):
        qs = AnomalyEvent.objects.all()
        status = request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return json_response([x.to_view() for x in qs[:500]])

    @auth('netmon.device.edit')
    def patch(self, request):
        form, error = JsonParser(
            Argument('id', type=int, help='请指定操作对象'),
            Argument('status', help='请指定状态'),
        ).parse(request.body)
        if error is None:
            data = {'status': form.status}
            if form.status == 'resolved':
                data['resolved_at'] = human_datetime()
            AnomalyEvent.objects.filter(pk=form.id).update(**data)
        return json_response(error=error)


# ------------------------------------------------------------------ 告警规则 -----
class AlertRuleView(View):
    @auth('netmon.device.view')
    def get(self, request):
        return json_response([x.to_view() for x in AlertRule.objects.all()])

    @auth('netmon.device.edit')
    def post(self, request):
        form, error = JsonParser(
            Argument('id', type=int, required=False),
            Argument('name', help='请输入规则名称'),
            Argument('group_id', type=int, required=False),
            Argument('device_id', type=int, required=False),
            Argument('metric_key', help='请选择监控指标'),
            Argument('operator', help='请选择比较符'),
            Argument('threshold', type=float, help='请输入阈值'),
            Argument('consecutive_times', type=int, default=1),
            Argument('level', default='warning'),
            Argument('notify_grp', type=list, default=[]),
            Argument('notify_mode', type=list, default=[]),
        ).parse(request.body)
        if error is None:
            form.notify_grp = json.dumps(form.notify_grp)
            form.notify_mode = json.dumps(form.notify_mode)
            if form.id:
                AlertRule.objects.filter(pk=form.id).update(**{k: v for k, v in form.items() if k != 'id'})
            else:
                AlertRule.objects.create(created_by=request.user, **{k: v for k, v in form.items() if k != 'id'})
        return json_response(error=error)

    @auth('netmon.device.del')
    def delete(self, request):
        form, error = JsonParser(Argument('id', type=int, help='请指定操作对象')).parse(request.GET)
        if error is None:
            AlertRule.objects.filter(pk=form.id).delete()
        return json_response(error=error)


# ------------------------------------------------------------------ 自动发现 -----
@auth('netmon.device.add')
def start_discovery(request):
    form, error = JsonParser(Argument('cidr', help='请输入待扫描网段，如 192.168.1.0/24')).parse(request.body)
    if error:
        return json_response(error=error)
    task_id = uuid.uuid4().hex[:12]
    Thread(target=discovery.scan_network, args=(task_id, form.cidr), daemon=True).start()
    return json_response({'task_id': task_id})


@auth('netmon.device.view')
def get_discovery_result(request):
    task_id = request.GET.get('task_id')
    if not task_id:
        return json_response(error='请指定 task_id')
    return json_response(discovery.get_scan_result(task_id))


@auth('netmon.device.add')
def import_discovery(request):
    form, error = JsonParser(
        Argument('devices', type=list, help='请选择要导入的设备'),
        Argument('group_id', type=int, required=False),
    ).parse(request.body)
    if error:
        return json_response(error=error)
    created = 0
    for item in form.devices:
        if Device.objects.filter(ip=item['ip']).exists():
            continue
        Device.objects.create(
            name=item.get('hostname') or item['ip'], ip=item['ip'],
            category=item.get('category_guess', 'other'), group_id=form.group_id,
            monitor_type='ping', created_by=request.user
        )
        created += 1
    return json_response({'created': created})


# ------------------------------------------------------------------ 维护窗口 -----
class MaintenanceWindowView(View):
    @auth('netmon.device.view')
    def get(self, request):
        return json_response([x.to_view() for x in MaintenanceWindow.objects.all()])

    @auth('netmon.device.edit')
    def post(self, request):
        form, error = JsonParser(
            Argument('id', type=int, required=False),
            Argument('name', help='请输入维护窗口名称'),
            Argument('group_id', type=int, required=False),
            Argument('device_id', type=int, required=False),
            Argument('start_at', help='请选择开始时间'),
            Argument('end_at', help='请选择结束时间'),
            Argument('reason', required=False),
        ).parse(request.body)
        if error is None:
            device_id = form.pop('id', None)
            if device_id:
                MaintenanceWindow.objects.filter(pk=device_id).update(**form)
            else:
                MaintenanceWindow.objects.create(created_by=request.user, **form)
        return json_response(error=error)

    @auth('netmon.device.del')
    def delete(self, request):
        form, error = JsonParser(Argument('id', type=int, help='请指定操作对象')).parse(request.GET)
        if error is None:
            MaintenanceWindow.objects.filter(pk=form.id).delete()
        return json_response(error=error)


# ------------------------------------------------------------------ 自动化处置 -----
class RemediationActionView(View):
    @auth('netmon.device.view')
    def get(self, request):
        return json_response([x.to_view() for x in RemediationAction.objects.all()])

    @auth('netmon.device.edit')
    def post(self, request):
        form, error = JsonParser(
            Argument('id', type=int, required=False),
            Argument('name', help='请输入处置动作名称'),
            Argument('device_id', type=int, required=False),
            Argument('group_id', type=int, required=False),
            Argument('metric_key', required=False),
            Argument('level', default='critical'),
            Argument('script', help='请输入处置脚本内容'),
            Argument('cooldown_minutes', type=int, default=15),
        ).parse(request.body)
        if error is None:
            action_id = form.pop('id', None)
            if action_id:
                RemediationAction.objects.filter(pk=action_id).update(**form)
            else:
                RemediationAction.objects.create(created_by=request.user, **form)
        return json_response(error=error)

    @auth('netmon.device.del')
    def delete(self, request):
        form, error = JsonParser(Argument('id', type=int, help='请指定操作对象')).parse(request.GET)
        if error is None:
            RemediationAction.objects.filter(pk=form.id).delete()
        return json_response(error=error)


@auth('netmon.device.view')
def get_remediation_logs(request):
    qs = RemediationLog.objects.all()[:300]
    return json_response([x.to_view() for x in qs])


# ------------------------------------------------------------------ 报表管理 -----
class ReportView(View):
    @auth('netmon.report.view')
    def get(self, request):
        return json_response([x.to_view() for x in Report.objects.all()])

    @auth('netmon.report.edit')
    def post(self, request):
        form, error = JsonParser(
            Argument('id', type=int, required=False),
            Argument('name', help='请输入报表名称'),
            Argument('report_type', default='daily'),
            Argument('group_id', type=int, required=False),
            Argument('recipients', type=list, default=[]),
        ).parse(request.body)
        if error is None:
            form.recipients = json.dumps(form.recipients)
            if form.id:
                Report.objects.filter(pk=form.id).update(**{k: v for k, v in form.items() if k != 'id'})
            else:
                Report.objects.create(created_by=request.user, **{k: v for k, v in form.items() if k != 'id'})
        return json_response(error=error)

    @auth('netmon.report.del')
    def delete(self, request):
        form, error = JsonParser(Argument('id', type=int, help='请指定操作对象')).parse(request.GET)
        if error is None:
            Report.objects.filter(pk=form.id).delete()
        return json_response(error=error)


@auth('netmon.report.edit')
def generate_report(request):
    form, error = JsonParser(
        Argument('id', type=int, help='请指定报表'),
        Argument('period_start', required=False),
        Argument('period_end', required=False),
    ).parse(request.body)
    if error:
        return json_response(error=error)
    report = Report.objects.filter(pk=form.id).first()
    if not report:
        return json_response(error='报表不存在')
    period_end = form.period_end or human_datetime()
    period_start = form.period_start or (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    record = report_builder.build_report(report, period_start, period_end)
    return json_response(record.to_view())


@auth('netmon.report.view')
def get_report_records(request):
    report_id = request.GET.get('report_id')
    qs = ReportRecord.objects.all()
    if report_id:
        qs = qs.filter(report_id=report_id)
    return json_response([x.to_view() for x in qs[:200]])


@auth('netmon.report.view')
def download_report(request):
    record_id = request.GET.get('id')
    record = ReportRecord.objects.filter(pk=record_id).first()
    if not record or not os.path.exists(record.file_path):
        return json_response(error='报表文件不存在')
    from django.http import FileResponse
    return FileResponse(
        open(record.file_path, 'rb'), as_attachment=True,
        filename=os.path.basename(record.file_path)
    )


# ── 网络工具箱 ──

@auth('netmon.device.view')
def tool_ping(request):
    form, error = JsonParser(
        Argument('target', help='请输入目标地址'),
        Argument('count', type=int, default=4),
    ).parse(request.body)
    if error:
        return json_response(error=error)
    count = max(1, min(form.count, 20))
    cmd = f'ping -n {count} -w 1000 {form.target}' if os.name == 'nt' else f'ping -c {count} -W 1 {form.target}'
    try:
        task = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=count + 5)
        return json_response({'exit_code': task.returncode, 'output': task.stdout + task.stderr})
    except subprocess.TimeoutExpired:
        return json_response({'exit_code': -1, 'output': 'Ping 执行超时'})
    except Exception as e:
        return json_response({'exit_code': -1, 'output': f'执行异常：{e}'})


@auth('netmon.device.view')
def tool_traceroute(request):
    form, error = JsonParser(
        Argument('target', help='请输入目标地址'),
        Argument('max_hops', type=int, default=30),
    ).parse(request.body)
    if error:
        return json_response(error=error)
    max_hops = max(1, min(form.max_hops, 50))
    if os.name == 'nt':
        cmd = f'tracert -d -h {max_hops} {form.target}'
    else:
        cmd = f'traceroute -m {max_hops} -w 1 -q 1 {form.target}'
    try:
        task = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=max_hops + 10)
        return json_response({'exit_code': task.returncode, 'output': task.stdout + task.stderr})
    except subprocess.TimeoutExpired:
        return json_response({'exit_code': -1, 'output': 'Traceroute 执行超时'})
    except Exception as e:
        return json_response({'exit_code': -1, 'output': f'执行异常：{e}'})


@auth('netmon.device.view')
def tool_port_test(request):
    form, error = JsonParser(
        Argument('host', help='请输入主机地址'),
        Argument('port', type=int, help='请输入端口号'),
        Argument('timeout', type=float, default=3),
    ).parse(request.body)
    if error:
        return json_response(error=error)
    import socket as _socket
    try:
        sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        sock.settimeout(form.timeout)
        start = datetime.now()
        result = sock.connect_ex((form.host, form.port))
        elapsed = round((datetime.now() - start).total_seconds() * 1000, 1)
        sock.close()
        if result == 0:
            return json_response({'reachable': True, 'elapsed_ms': elapsed, 'message': f'端口 {form.port} 开放，耗时 {elapsed}ms'})
        return json_response({'reachable': False, 'elapsed_ms': elapsed, 'message': f'端口 {form.port} 不可达，错误码 {result}'})
    except _socket.timeout:
        return json_response({'reachable': False, 'elapsed_ms': None, 'message': '连接超时'})
    except Exception as e:
        return json_response({'reachable': False, 'elapsed_ms': None, 'message': f'异常：{e}'})


@auth('netmon.device.view')
def tool_dns_lookup(request):
    form, error = JsonParser(
        Argument('domain', help='请输入域名'),
        Argument('record_type', default='A'),
    ).parse(request.body)
    if error:
        return json_response(error=error)
    import socket as _socket
    try:
        if form.record_type.upper() in ('A', 'AAAA'):
            results = _socket.getaddrinfo(form.domain, None)
            ips = sorted(set(r[4][0] for r in results))
            return json_response({'records': ips, 'output': '\n'.join(ips)})
        else:
            cmd = f'nslookup -type={form.record_type} {form.domain}' if os.name == 'nt' else f'dig {form.domain} {form.record_type} +short'
            task = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            return json_response({'records': [], 'output': task.stdout + task.stderr})
    except _socket.gaierror as e:
        return json_response({'records': [], 'output': f'域名解析失败：{e}'})
    except Exception as e:
        return json_response({'records': [], 'output': f'异常：{e}'})


# ── 设备配置备份 ──

VENDOR_BACKUP_COMMANDS = {
    'Huawei': 'display current-configuration',
    'H3C': 'display current-configuration',
    'Cisco': 'show running-config',
    'Ruijie': 'show running-config',
    'ZTE': 'show running-config',
    'default': 'show running-config',
}


@auth('netmon.device.view')
def get_config_backups(request):
    device_id = request.GET.get('device_id')
    qs = ConfigBackup.objects.all()
    if device_id:
        qs = qs.filter(device_id=device_id)
    return json_response([x.to_view() for x in qs[:200]])


@auth('netmon.device.edit')
def trigger_config_backup(request):
    form, error = JsonParser(
        Argument('device_id', type=int, help='参数错误'),
    ).parse(request.body)
    if error:
        return json_response(error=error)
    device = Device.objects.filter(pk=form.device_id).first()
    if not device:
        return json_response(error='设备不存在')
    if not device.host_id:
        return json_response(error='设备未关联主机，无法通过SSH采集配置')
    from libs.ssh_executor import ssh_exec
    vendor = device.extra.get('vendor', '') if isinstance(device.extra, dict) else ''
    command = VENDOR_BACKUP_COMMANDS.get(vendor, VENDOR_BACKUP_COMMANDS['default'])
    exit_code, output = ssh_exec(device.host, command, retries=1)
    if exit_code != 0:
        return json_response(error=f'配置采集失败：{output[:500]}')
    import hashlib
    config_text = output.strip()
    config_hash = hashlib.md5(config_text.encode()).hexdigest()
    last = ConfigBackup.objects.filter(device=device).first()
    if last and last.config_hash == config_hash:
        return json_response({'message': '配置未变化，跳过存储', 'hash': config_hash, 'changed': False})
    backup = ConfigBackup.objects.create(
        device=device, config_text=config_text, config_hash=config_hash,
        config_size=len(config_text), is_auto=False, created_by=request.user
    )
    return json_response({'message': '配置备份成功', 'id': backup.id, 'hash': config_hash, 'changed': True, 'size': len(config_text)})


@auth('netmon.device.view')
def get_config_backup_detail(request):
    backup_id = request.GET.get('id')
    backup = ConfigBackup.objects.filter(pk=backup_id).first()
    if not backup:
        return json_response(error='备份记录不存在')
    return json_response({'id': backup.id, 'device_name': backup.device.name, 'config_text': backup.config_text, 'created_at': backup.created_at, 'config_hash': backup.config_hash})


@auth('netmon.device.view')
def diff_config_backups(request):
    form, error = JsonParser(
        Argument('base_id', type=int, help='请选择基准版本'),
        Argument('compare_id', type=int, help='请选择对比版本'),
    ).parse(request.body)
    if error:
        return json_response(error=error)
    base = ConfigBackup.objects.filter(pk=form.base_id).first()
    compare = ConfigBackup.objects.filter(pk=form.compare_id).first()
    if not base or not compare:
        return json_response(error='备份记录不存在')
    import difflib
    base_lines = base.config_text.splitlines(keepends=True)
    compare_lines = compare.config_text.splitlines(keepends=True)
    diff = list(difflib.unified_diff(base_lines, compare_lines, fromfile=f'基准 {base.created_at}', tofile=f'对比 {compare.created_at}', lineterm=''))
    return json_response({
        'diff': '\n'.join(diff),
        'is_same': base.config_hash == compare.config_hash,
        'base_at': base.created_at,
        'compare_at': compare.created_at,
    })
