# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
from apps.netmon.models import Device
from apps.netmon import collectors, anomaly, remediation
from apps.notify.models import Notify
import logging
import json


def netmon_worker_handler(job):
    """由 apps/exec/management/commands/runworker.py 统一的线程池调度执行。
    流程：读取设备 -> 采集指标 -> 写时序数据并做异常检测 -> 更新设备状态 -> 触发通知
    """
    payload = json.loads(job)
    device = Device.objects.filter(pk=payload['device_id'], is_active=True).first()
    if not device:
        return
    try:
        metrics = collectors.collect(device)
    except Exception as e:
        logging.warning(f'netmon 采集异常 device={device.ip}: {e}')
        metrics = None

    if metrics is None:
        # 采集失败（例如 ping 不通）视为离线
        device.status = 'offline'
        device.save(update_fields=['status'])
        return

    events = anomaly.analyze(device, metrics)
    anomaly.resolve_device_status(device, metrics, events)

    for event in events:
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
