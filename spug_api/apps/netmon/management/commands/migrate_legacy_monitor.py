# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
"""
一次性数据迁移命令：把旧版"监控中心"(apps.monitor / detections 表)中的监控项
迁移为统一后的"IT资源监控"(apps.netmon.models.Device)记录，保证本次模块合并
不丢失任何已有的监控配置和告警设置。

用法：
    python manage.py migrate_legacy_monitor          # 正式执行迁移
    python manage.py migrate_legacy_monitor --dry-run # 仅预览，不写入数据库

说明：
    * 本命令通过原生 SQL 直接读取 detections 表，不依赖 apps.monitor（该应用已
      随本次模块统一被移除），因此在旧应用代码删除后依然可以安全运行。
    * 迁移是幂等的：同一条 Detection 目标已存在对应 Device（相同 name）时会跳过。
    * 迁移只做"读旧表 -> 写新表"，不会删除或修改 detections 原表，你可以在确认
      新版 IT资源监控运行正常后自行归档/清理旧表。
"""
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from apps.netmon.models import Device
from apps.host.models import Host
from apps.account.models import User
import json

# 旧 Detection.type -> 新 Device.monitor_type
TYPE_MAP = {
    '1': 'http',        # 站点检测
    '2': 'port',         # 端口检测
    '3': 'process',       # 进程检测
    '4': 'shell',         # 自定义脚本(退出码)
    '5': 'ping_check',    # Ping检测
    '6': 'docker',        # Docker检测
    '7': 'database',      # 数据库检测
    '8': 'log',           # 日志监控
}
HOST_BASED_TYPES = {'3', '4', '6', '8'}  # 这些类型的 target 存的是 host_id


class Command(BaseCommand):
    help = '将旧版监控中心(detections表)的数据迁移为统一后的 IT资源监控(Device) 记录'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='只打印将要执行的迁移，不实际写入')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if not self._table_exists('detections'):
            self.stdout.write(self.style.WARNING('未发现 detections 表，可能已迁移过或本来就是全新安装，无需迁移。'))
            return

        rows = self._fetch_detections()
        if not rows:
            self.stdout.write(self.style.WARNING('detections 表中没有数据，无需迁移。'))
            return

        fallback_user = User.objects.filter(is_supper=True).first() or User.objects.first()
        created, skipped, failed = 0, 0, 0

        for row in rows:
            try:
                targets = json.loads(row['targets'] or '[]')
            except (TypeError, ValueError):
                targets = []
            new_type = TYPE_MAP.get(row['type'])
            if not new_type:
                self.stdout.write(self.style.WARNING(f"跳过未知类型的监控项 id={row['id']} type={row['type']}"))
                failed += 1
                continue

            for target in targets:
                target = str(target)
                device_name = f"{row['name']}-{target}" if len(targets) > 1 else row['name']
                if Device.objects.filter(name=device_name).exists():
                    skipped += 1
                    continue

                host_id, ip, extra = None, target, row['extra'] or ''
                if row['type'] in HOST_BASED_TYPES:
                    host = Host.objects.filter(pk=target).first()
                    if not host:
                        self.stdout.write(self.style.WARNING(
                            f"监控项【{row['name']}】关联的主机(id={target})已不存在，跳过该条目"))
                        failed += 1
                        continue
                    host_id, ip = host.id, host.hostname
                    if row['type'] == '3':
                        extra_json = {'keyword': row['extra'] or ''}
                    elif row['type'] == '6':
                        extra_json = {'container': row['extra'] or ''}
                    elif row['type'] == '8':
                        path, _, keyword = (row['extra'] or '').partition('||')
                        extra_json = {'path': path, 'keyword': keyword, 'tail_lines': 200}
                    else:  # '4' shell，保持原始脚本文本，不做 JSON 包装
                        extra_json = None
                    extra = row['extra'] if extra_json is None else json.dumps(extra_json, ensure_ascii=False)
                elif row['type'] in ('2', '7'):
                    extra = json.dumps({'port': row['extra']}, ensure_ascii=False)
                elif row['type'] == '1':
                    extra = json.dumps(
                        {'url': target, 'timeout_limit_ms': int(row['extra'])} if row['extra'] else {'url': target},
                        ensure_ascii=False)
                    ip = target

                self.stdout.write(
                    f"{'[预览] ' if dry_run else ''}迁移【{row['name']}】-> Device(name={device_name}, "
                    f"monitor_type={new_type}, ip={ip}, host_id={host_id})")
                if dry_run:
                    created += 1
                    continue

                with transaction.atomic():
                    Device.objects.create(
                        name=device_name, ip=ip or '0.0.0.0', category='other', monitor_type=new_type,
                        host_id=host_id, extra=extra, rate=max(int(row['rate'] or 5) * 60, 60),
                        threshold=row['threshold'] or 3, quiet=row['quiet'] or 24 * 60,
                        notify_grp=row['notify_grp'] or '[]', notify_mode=row['notify_mode'] or '[]',
                        is_active=bool(row['is_active']), desc=row['desc'],
                        created_by=fallback_user,
                    )
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f"迁移完成：{'（预览模式，未实际写入）' if dry_run else ''}"
            f"新建 {created} 条，跳过(已存在) {skipped} 条，失败 {failed} 条。"
        ))
        if not dry_run and created:
            self.stdout.write(self.style.WARNING(
                '提示：detections 原表数据未被删除，请在确认新版 IT资源监控运行正常后自行归档/清理。'))

    @staticmethod
    def _table_exists(table_name):
        return table_name in connection.introspection.table_names()

    @staticmethod
    def _fetch_detections():
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT id, name, type, targets, extra, `desc`, is_active, rate, threshold, quiet, '
                'notify_mode, notify_grp FROM detections'
            )
            columns = [c[0] for c in cursor.description]
            return [dict(zip(columns, r)) for r in cursor.fetchall()]
