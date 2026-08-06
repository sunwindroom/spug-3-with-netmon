# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Released under the AGPL-3.0 License.
"""
统一监控调度器
--------------
本文件由原 apps/monitor/scheduler.py 迁移合并而来：monitor(Detection) 与
netmon(Device) 曾是两套并行的定时调度实现，现已统一为对 Device 表的单一调度，
不再区分"监控中心"和"IT资源监控"两套数据源。
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.interval import IntervalTrigger
from django_redis import get_redis_connection
from django.conf import settings
from django.db import connections
from django.db.utils import DatabaseError
from apps.netmon.models import Device
from apps.netmon.anomaly import check_escalations
from libs import AttrDict
from datetime import datetime, timedelta
from random import randint
import logging
import json

NETMON_KEY = settings.NETMON_KEY
NETMON_WORKER_KEY = settings.NETMON_WORKER_KEY


class Scheduler:
    """统一调度器：管理全部 netmon(Device) 定时任务，涵盖指标采集与可用性检测两类。
    任务通过 Redis 队列分发到 runworker 线程池异步执行。
    """
    timezone = settings.TIME_ZONE

    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone=self.timezone, executors={'default': ThreadPoolExecutor(30)})

    def _dispatch(self, device_id):
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
            for item in Device.objects.filter(is_active=True):
                trigger = IntervalTrigger(seconds=int(item.rate), timezone=self.timezone)
                self.scheduler.add_job(
                    self._dispatch, trigger, id=f'netmon_{item.id}', args=(item.id,),
                    next_run_time=datetime.now() + timedelta(seconds=randint(0, 30))
                )
            connections.close_all()
        except DatabaseError:
            pass

    def run(self):
        rds_cli = get_redis_connection()
        self._init()
        rds_cli.delete(NETMON_KEY)
        logging.warning('Running unified monitor scheduler (netmon)')
        while True:
            _, data = rds_cli.brpop([NETMON_KEY])
            task = AttrDict(json.loads(data))
            job_id = f'netmon_{task.id}'
            if task.action in ('add', 'modify'):
                trigger = IntervalTrigger(seconds=int(task.rate), timezone=self.timezone)
                self.scheduler.add_job(
                    self._dispatch, trigger, id=job_id, args=(task.id,), replace_existing=True
                )
            elif task.action == 'remove':
                job = self.scheduler.get_job(job_id)
                if job:
                    job.remove()
