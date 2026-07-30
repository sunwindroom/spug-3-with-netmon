# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
"""
定时生成报表。建议通过 crontab 或 spug 现有的『任务计划』(apps.schedule) 每天调度一次：
    python manage.py gen_netmon_reports
会自动为到期的日报/周报/月报生成 xlsx 并发送通知给订阅人（notify_grp）。
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.netmon.models import Report
from apps.netmon import reports as report_builder
from apps.notify.models import Notify
from libs import human_datetime
from datetime import datetime, timedelta
import logging


class Command(BaseCommand):
    help = 'Generate due netmon reports (daily/weekly/monthly)'

    def handle(self, *args, **options):
        now = datetime.now()
        for report in Report.objects.filter(is_active=True):
            if not self._is_due(report, now):
                continue
            period_start, period_end = self._period(report, now)
            try:
                record = report_builder.build_report(report, period_start, period_end)
                Notify.make_system_notify(
                    f'报表已生成：{report.name}',
                    f'统计周期 {period_start} ~ {period_end}，可前往「报表管理」下载查看（文件：{record.file_path}）。'
                )
            except Exception as e:
                logging.warning(f'生成报表失败 report={report.name}: {e}')

    @staticmethod
    def _is_due(report, now):
        if report.report_type == 'daily':
            return True
        if report.report_type == 'weekly':
            return now.weekday() == 0  # 每周一生成上周报表
        if report.report_type == 'monthly':
            return now.day == 1
        return False  # manual 类型不自动生成

    @staticmethod
    def _period(report, now):
        if report.report_type == 'daily':
            start = (now - timedelta(days=1)).strftime('%Y-%m-%d 00:00:00')
            end = now.strftime('%Y-%m-%d 00:00:00')
        elif report.report_type == 'weekly':
            start = (now - timedelta(days=7)).strftime('%Y-%m-%d 00:00:00')
            end = now.strftime('%Y-%m-%d 00:00:00')
        else:
            start = (now - timedelta(days=30)).strftime('%Y-%m-%d 00:00:00')
            end = now.strftime('%Y-%m-%d 00:00:00')
        return start, end
