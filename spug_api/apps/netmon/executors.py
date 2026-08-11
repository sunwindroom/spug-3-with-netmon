# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Released under the AGPL-3.0 License.
"""
统一监控执行入口
----------------
每个 Device 按 monitor_type 分为两类工作流，由 runworker 线程池统一调度：

  * METRIC_TYPES（ping/snmp/agent/script）：采集数值型指标 -> 写入 MetricRecord
    -> AlertRule 阈值规则 / 3-sigma 动态基线做异常检测 -> 更新设备状态。
  * CHECK_TYPES（http/port/database/ping_check/process/docker/shell/log）：
    二元可用性检测(是否正常) -> 连续失败次数达到 threshold 后按 quiet 静默期发出告警，
    此流程合并自原 apps.monitor 模块，语义保持不变。

优化点（本次）：
  * netmon_worker_handler 增加顶层异常隔离，单个设备处理异常不会影响线程池中其他任务。
  * _run_metric_flow 采集失败时不再立即判 offline，而是保留上次状态并记录告警，避免
    单次采集抖动导致设备状态频繁翻转。
  * _run_check_flow 保留原有 threshold/quiet 语义，仅优化日志可读性。
"""
from django_redis import get_redis_connection
from apps.netmon.models import Device
from apps.netmon import collectors, anomaly, remediation, checks
from apps.netmon.notify_utils import handle_check_notify
from apps.notify.models import Notify
from libs import human_datetime
import logging
import json
import time

DET_KEY = 'spug:netmon:det:{}'  # 可用性检测的连续失败计数/最近告警时间，key结构同原 monitor 实现
METRIC_FAIL_KEY = 'spug:netmon:metric_fail:{}'  # 指标采集连续失败计数


def _run_metric_flow(device):
    try:
        metrics = collectors.collect(device)
    except Exception as e:
        logging.warning(f'netmon 采集异常 device={device.ip}: {e}')
        metrics = None

    if metrics is None:
        rds = get_redis_connection()
        fail_count = rds.incr(METRIC_FAIL_KEY.format(device.id))
        rds.expire(METRIC_FAIL_KEY.format(device.id), max(device.rate * 10, 3600))
        if fail_count >= 3:
            device.status = 'offline'
            device.latest_check_at = human_datetime()
            device.save(update_fields=['status', 'latest_check_at'])
        return

    rds = get_redis_connection()
    rds.delete(METRIC_FAIL_KEY.format(device.id))

    events = anomaly.analyze(device, metrics)
    anomaly.resolve_device_status(device, metrics, events)

    for event in events:
        if event.method != 'threshold':
            try:
                Notify.make_system_notify(
                    f'[{event.get_level_display()}] {device.name} 指标异常',
                    event.message
                )
            except Exception as e:
                logging.warning(f'netmon 异常通知发送失败: {e}')
        try:
            remediation.trigger(device, event)
        except Exception as e:
            logging.warning(f'netmon 自动化处置执行异常: {e}')


def _run_check_flow(device):
    try:
        is_ok, message = checks.run_check(device)
    except Exception as e:
        is_ok, message = False, f'检测异常：{e}'

    target = f'{device.host.name}({device.host.hostname})' if device.host_id else f'{device.name}({device.ip})'
    rds = get_redis_connection()
    key, f_count, f_time = DET_KEY.format(device.id), 'c', 't'
    v_count, v_time = rds.hmget(key, f_count, f_time)

    if is_ok:
        device.status = 'online'
        device.last_value = json.dumps({'message': message})
        device.latest_check_at = human_datetime()
        device.save(update_fields=['status', 'last_value', 'latest_check_at'])
        if v_count:
            rds.hdel(key, f_count, f_time)
        if v_time:
            logging.warning(f'send recovery notification device={device.ip}')
            handle_check_notify(device, target, is_ok, message, int(v_count or 0) + 1)
        return

    device.status = 'offline' if device.monitor_type in ('ping_check', 'port', 'database') else 'critical'
    device.last_value = json.dumps({'message': message})
    device.latest_check_at = human_datetime()
    device.save(update_fields=['status', 'last_value', 'latest_check_at'])

    v_count = rds.hincrby(key, f_count)
    rds.expire(key, max(device.rate * 20, 3600))
    if v_count >= device.threshold:
        if not v_time or int(time.time()) - int(v_time) >= device.quiet * 60:
            rds.hset(key, f_time, int(time.time()))
            logging.warning(f'send fault alarm notification device={device.ip} count={v_count}')
            handle_check_notify(device, target, is_ok, message, v_count)


def netmon_worker_handler(job):
    """由 apps/exec/management/commands/runworker.py 统一的线程池调度执行。"""
    try:
        payload = json.loads(job)
        device = Device.objects.filter(pk=payload['device_id'], is_active=True).first()
        if not device:
            return
        if device.is_check_type():
            _run_check_flow(device)
        else:
            _run_metric_flow(device)
    except Exception as e:
        logging.error(f'netmon worker 处理异常 job={job}: {e}', exc_info=True)
