# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Released under the AGPL-3.0 License.
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.interval import IntervalTrigger
from django_redis import get_redis_connection
from django.conf import settings
from django.db import connections
from django.db.utils import DatabaseError
from apps.monitor.models import Detection
from apps.netmon.models import Device
from apps.netmon.anomaly import check_escalations
from libs import AttrDict, human_datetime
from datetime import datetime, timedelta
from random import randint
import logging
import json

MONITOR_WORKER_KEY = settings.MONITOR_WORKER_KEY
NETMON_WORKER_KEY = settings.NETMON_WORKER_KEY


class Scheduler:
    """统一调度器：同时管理 monitor(Detection) 和 netmon(Device) 的定时采集任务。
    两类任务分别通过各自的 Redis 队列分发到 runworker 线程池异步执行。
    """
    timezone = settings.TIME_ZONE

    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone=self.timezone, executors={'default': ThreadPoolExecutor(30)})

    def _dispatch_monitor(self, task_id, tp, targets, extra, threshold, quiet):
        Detection.objects.filter(pk=task_id).update(latest_run_time=human_datetime())
        rds_cli = get_redis_connection()
        for t in json.loads(targets):
            rds_cli.rpush(MONITOR_WORKER_KEY, json.dumps([task_id, tp, t, extra, threshold, quiet]))
        connections.close_all()

    def _dispatch_netmon(self, device_id):
        rds_cli = get_redis_connection()
        rds_cli.rpush(NETMON_WORKER_KEY, json.dumps({'device_id': device_id}))
        connections.close_all()

    def _safe_check_escalations(self):
        try:
            check_escalations()
        except DatabaseError:
            pass
        finally:
            connections.close_all()

    def _init(self):
        self.scheduler.start()
        self.scheduler.add_job(
            self._safe_check_escalations, IntervalTrigger(seconds=60, timezone=self.timezone), id='netmon_escalation'
        )
        try:
            for item in Detection.objects.filter(is_active=True):
                now = datetime.now()
                trigger = IntervalTrigger(minutes=int(item.rate), timezone=self.timezone)
                self.scheduler.add_job(
                    self._dispatch_monitor,
                    trigger,
                    id=str(item.id),
                    args=(item.id, item.type, item.targets, item.extra, item.threshold, item.quiet),
                    next_run_time=now + timedelta(seconds=randint(0, 60))
                )
            connections.close_all()
        except DatabaseError:
            pass
        try:
            for item in Device.objects.filter(is_active=True):
                trigger = IntervalTrigger(seconds=int(item.rate), timezone=self.timezone)
                self.scheduler.add_job(
                    self._dispatch_netmon, trigger, id=f'netmon_{item.id}', args=(item.id,),
                    next_run_time=datetime.now() + timedelta(seconds=randint(0, 30))
                )
            connections.close_all()
        except DatabaseError:
            pass

    def run(self):
        rds_cli = get_redis_connection()
        self._init()
        rds_cli.delete(settings.MONITOR_KEY, settings.NETMON_KEY)
        logging.warning('Running unified scheduler (monitor + netmon)')
        while True:
            _, data = rds_cli.brpop([settings.MONITOR_KEY, settings.NETMON_KEY])
            raw = json.loads(data)
            key_used = _.decode() if isinstance(_, bytes) else _
            task = AttrDict(raw)
            if key_used == settings.NETMON_KEY:
                job_id = f'netmon_{task.id}'
                if task.action in ('add', 'modify'):
                    trigger = IntervalTrigger(seconds=int(task.rate), timezone=self.timezone)
                    self.scheduler.add_job(
                        self._dispatch_netmon, trigger, id=job_id, args=(task.id,), replace_existing=True
                    )
                elif task.action == 'remove':
                    job = self.scheduler.get_job(job_id)
                    if job:
                        job.remove()
            else:
                if task.action in ('add', 'modify'):
                    trigger = IntervalTrigger(minutes=int(task.rate), timezone=self.timezone)
                    self.scheduler.add_job(
                        self._dispatch_monitor,
                        trigger,
                        id=str(task.id),
                        args=(task.id, task.type, task.targets, task.extra, task.threshold, task.quiet),
                        replace_existing=True
                    )
                elif task.action == 'remove':
                    job = self.scheduler.get_job(str(task.id))
                    if job:
                        job.remove()
