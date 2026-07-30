from django.core.management.base import BaseCommand
from apps.exec.models import ExecTemplate
from apps.account.models import User
from apps.exec.management.commands.monitor_templates_data import MONITOR_TEMPLATES
import json


class Command(BaseCommand):
    help = '导入监控脚本模板到ExecTemplate表'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true', default=False,
            help='强制覆盖已存在的同名模板'
        )
        parser.add_argument(
            '--user', type=str, default='admin',
            help='模板创建者用户名，默认admin'
        )

    def handle(self, *args, **options):
        force = options['force']
        username = options['user']

        user = User.objects.filter(username=username).first()
        if not user:
            self.stdout.write(self.style.ERROR(f'用户 {username} 不存在，请先创建用户'))
            return

        created_count = 0
        skipped_count = 0
        updated_count = 0

        for tpl_data in MONITOR_TEMPLATES:
            name = tpl_data['name']
            tpl_type = tpl_data['type']

            existing = ExecTemplate.objects.filter(name=name, type=tpl_type).first()

            if existing:
                if force:
                    existing.type = tpl_type
                    existing.body = tpl_data['body']
                    existing.interpreter = tpl_data.get('interpreter', 'sh')
                    existing.desc = tpl_data.get('desc', '')
                    existing.parameters = json.dumps(tpl_data.get('parameters', []))
                    existing.updated_by = user
                    from libs.utils import human_datetime
                    existing.updated_at = human_datetime()
                    existing.save()
                    updated_count += 1
                    self.stdout.write(self.style.WARNING(f'  更新: [{tpl_type}] {name}'))
                else:
                    skipped_count += 1
                    self.stdout.write(f'  跳过: [{tpl_type}] {name} (已存在)')
            else:
                ExecTemplate.objects.create(
                    name=name,
                    type=tpl_type,
                    body=tpl_data['body'],
                    interpreter=tpl_data.get('interpreter', 'sh'),
                    host_ids='[]',
                    desc=tpl_data.get('desc', ''),
                    parameters=json.dumps(tpl_data.get('parameters', [])),
                    created_by=user
                )
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  创建: [{tpl_type}] {name}'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'导入完成! 新建: {created_count}, 更新: {updated_count}, 跳过: {skipped_count}'
        ))

        types = [x['type'] for x in ExecTemplate.objects.order_by('type').values('type').distinct()]
        self.stdout.write(f'当前模板类型: {", ".join(types)}')
        self.stdout.write(f'模板总数: {ExecTemplate.objects.count()}')