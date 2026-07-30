# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from django.db import connections
from django.db.utils import DatabaseError
from .models import Subnet
from . import scanner, predictor
import logging


SCAN_INTERVAL_MINUTES = 30  # 每个网段的存活/未授权设备扫描周期


class Scheduler:
    """独立的 IPAM 后台进程：周期性网段扫描（未授权设备/冲突检测） + 每日用量快照（预测性洞察）"""

    def __init__(self):
        self.scheduler = BlockingScheduler(executors={'default': ThreadPoolExecutor(10)})

    def _scan_all(self):
        try:
            for subnet in Subnet.objects.all():
                try:
                    scanner.scan_subnet(subnet)
                except Exception as e:
                    logging.warning(f'IPAM扫描异常 subnet={subnet.cidr}: {e}')
        except DatabaseError:
            pass
        finally:
            connections.close_all()

    def _snapshot(self):
        try:
            predictor.take_daily_snapshot()
        except DatabaseError:
            pass
        finally:
            connections.close_all()

    def run(self):
        self.scheduler.add_job(self._scan_all, IntervalTrigger(minutes=SCAN_INTERVAL_MINUTES), id='ipam_scan')
        self.scheduler.add_job(self._snapshot, CronTrigger(hour=0, minute=5), id='ipam_snapshot')
        logging.warning('Running ipam scheduler')
        self.scheduler.start()
