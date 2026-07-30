# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
from django.views.generic import View
from django.conf import settings
from django_redis import get_redis_connection
from libs import json_response, JsonParser, Argument, human_datetime, auth
from apps.monitor.models import Detection
from apps.monitor.executors import dispatch
from apps.setting.utils import AppSetting
from apps.alarm.models import Alarm
from datetime import datetime, timedelta
from statistics import mean
import json


class DetectionView(View):
    @auth('dashboard.dashboard.view|monitor.monitor.view')
    def get(self, request):
        detections = Detection.objects.all()
        groups = [x['group'] for x in detections.order_by('group').values('group').distinct()]
        return json_response({'groups': groups, 'detections': [x.to_view() for x in detections]})

    @auth('monitor.monitor.add|monitor.monitor.edit')
    def post(self, request):
        form, error = JsonParser(
            Argument('id', type=int, required=False),
            Argument('name', help='请输入任务名称'),
            Argument('group', help='请选择任务分组'),
            Argument('targets', type=list, filter=lambda x: len(x), help='请输入监控地址'),
            Argument('type', filter=lambda x: x in dict(Detection.TYPES), help='请选择监控类型'),
            Argument('extra', required=False),
            Argument('desc', required=False),
            Argument('rate', type=int, default=5),
            Argument('threshold', type=int, default=3),
            Argument('quiet', type=int, default=24 * 60),
            Argument('notify_grp', type=list, help='请选择报警联系组'),
            Argument('notify_mode', type=list, help='请选择报警方式'),
        ).parse(request.body)
        if error is None:
            if set(form.notify_mode).intersection(['1', '2', '6']):
                if not AppSetting.get_default('spug_push_key'):
                    return json_response(error='报警方式微信、短信、电话需要配置推送服务（系统设置/推送服务设置），请配置后再启用该报警方式。')

            form.targets = json.dumps(form.targets)
            form.notify_grp = json.dumps(form.notify_grp)
            form.notify_mode = json.dumps(form.notify_mode)
            if form.id:
                Detection.objects.filter(pk=form.id).update(
                    updated_at=human_datetime(),
                    updated_by=request.user,
                    **form)
                task = Detection.objects.filter(pk=form.id).first()
                if task and task.is_active:
                    form.action = 'modify'
                    rds_cli = get_redis_connection()
                    rds_cli.lpush(settings.MONITOR_KEY, json.dumps(form))
            else:
                dtt = Detection.objects.create(created_by=request.user, **form)
                form.action = 'add'
                form.id = dtt.id
                rds_cli = get_redis_connection()
                rds_cli.lpush(settings.MONITOR_KEY, json.dumps(form))
        return json_response(error=error)

    @auth('monitor.monitor.edit')
    def patch(self, request):
        form, error = JsonParser(
            Argument('id', type=int, help='请指定操作对象'),
            Argument('is_active', type=bool, required=False)
        ).parse(request.body, True)
        if error is None:
            Detection.objects.filter(pk=form.id).update(**form)
            if form.get('is_active') is not None:
                if form.is_active:
                    task = Detection.objects.filter(pk=form.id).first()
                    message = {'id': form.id, 'action': 'add'}
                    message.update(task.to_dict(selects=('targets', 'extra', 'rate', 'type', 'threshold', 'quiet')))
                else:
                    message = {'id': form.id, 'action': 'remove'}
                rds_cli = get_redis_connection()
                rds_cli.lpush(settings.MONITOR_KEY, json.dumps(message))
        return json_response(error=error)

    @auth('monitor.monitor.del')
    def delete(self, request):
        form, error = JsonParser(
            Argument('id', type=int, help='请指定操作对象')
        ).parse(request.GET)
        if error is None:
            task = Detection.objects.filter(pk=form.id).first()
            if task:
                if task.is_active:
                    return json_response(error='该监控项正在运行中，请先停止后再尝试删除')
                task.delete()
        return json_response(error=error)


@auth('monitor.monitor.add|monitor.monitor.edit')
def run_test(request):
    form, error = JsonParser(
        Argument('type', help='请选择监控类型'),
        Argument('targets', type=list, filter=lambda x: len(x), help='请输入监控地址'),
        Argument('extra', required=False)
    ).parse(request.body)
    if error is None:
        is_success, message = dispatch(form.type, form.targets[0], form.extra)
        return json_response({'is_success': is_success, 'message': message})
    return json_response(error=error)


def _build_target_status_list():
    response = []
    rds = get_redis_connection()
    for item in Detection.objects.all():
        data = {}
        for key in json.loads(item.targets):
            key = str(key)
            data[key] = {
                'id': f'{item.id}_{key}',
                'group': item.group,
                'name': item.name,
                'type': item.get_type_display(),
                'type_code': item.type,
                'target': key,
                'desc': item.desc,
                'status': '0',
                'latest_run_time': item.latest_run_time,
            }
            if item.is_active:
                if item.latest_run_time:
                    data[key]['status'] = '1'
                else:
                    data[key]['status'] = '10'
        if item.is_active:
            for key, val in rds.hgetall(f'spug:det:{item.id}').items():
                prefix, key = key.decode().split('_', 1)
                if key in data:
                    val = int(val)
                    if prefix == 'c':
                        if data[key]['status'] == '1':
                            data[key]['status'] = '2'
                        data[key]['count'] = val
                    elif prefix == 't':
                        date = datetime.fromtimestamp(val).strftime('%Y-%m-%d %H:%M:%S')
                        data[key].update(status='3', notified_at=date)
        response.extend(list(data.values()))
    return response


@auth('monitor.monitor.view')
def get_overview(request):
    return json_response(_build_target_status_list())


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


@auth('monitor.monitor.view')
def get_dashboard(request):
    """监控中心总览大屏：8类监控资源在线情况 + 主机性能图表 + 资源分布 + 资源总量统计"""
    # 延迟导入，避免 apps.monitor 在应用注册阶段对 apps.netmon/apps.host 产生加载期耦合
    from apps.netmon.models import Device
    from apps.host.models import HostExtend

    target_list = _build_target_status_list()
    type_stats = []
    for code, alias in Detection.TYPES:
        items = [x for x in target_list if x['type_code'] == code]
        total = len(items)
        fault = len([x for x in items if x['status'] == '3'])
        online = total - fault
        type_stats.append({
            'type': code, 'type_alias': alias, 'total': total, 'online': online,
            'rate': round(online / total * 100, 1) if total else 0.0,
        })

    since_1h = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
    recent_alerts_1h = Alarm.objects.filter(status='1', created_at__gte=since_1h).count()

    devices = list(Device.objects.all())
    bar_charts = {
        'traffic': [
            {'metric': '主机上行流量(Kb/s)', **_metric_stats(devices, 'net_out')},
            {'metric': '主机下行流量(Kb/s)', **_metric_stats(devices, 'net_in')},
        ],
        'load': [
            {'metric': '主机时延(ms)', **_metric_stats(devices, 'rtt')},
        ],
        'usage': [
            {'metric': '主机CPU使用率(%)', **_metric_stats(devices, 'cpu')},
            {'metric': '主机内存使用率(%)', **_metric_stats(devices, 'memory')},
            {'metric': '磁盘使用率(%)', **_metric_stats(devices, 'disk')},
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
    for d in devices:
        try:
            v = json.loads(d.last_value) if d.last_value else {}
        except (TypeError, ValueError):
            v = {}
        resource_totals['traffic_in_kbps'] += v.get('net_in', 0)
        resource_totals['traffic_out_kbps'] += v.get('net_out', 0)
    resource_totals = {k: round(v, 1) for k, v in resource_totals.items()}

    host_traffic = []
    for d in devices:
        try:
            v = json.loads(d.last_value) if d.last_value else {}
        except (TypeError, ValueError):
            v = {}
        total = (v.get('net_in', 0) or 0) + (v.get('net_out', 0) or 0)
        if total > 0:
            host_traffic.append({'name': d.name, 'ip': d.ip, 'value': round(total, 1)})
    host_traffic.sort(key=lambda x: -x['value'])

    return json_response({
        'type_stats': type_stats,
        'recent_alerts_1h': recent_alerts_1h,
        'resource_total_count': len(devices) + Detection.objects.count(),
        'bar_charts': bar_charts,
        'memory_distribution': _distribution(devices, 'memory'),
        'cpu_distribution': _distribution(devices, 'cpu'),
        'resource_totals': resource_totals,
        'host_traffic': host_traffic[:10],
    })
