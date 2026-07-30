# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
"""
手动（重新）执行监控脚本模板库的初始化。

正常情况下不需要手动运行本命令：apps.exec.apps.ExecConfig.ready() 已经注册了
post_migrate 信号，每次执行 `python manage.py migrate` / `updatedb` 都会自动静默
补种缺失的模板。本命令主要用于：
  * 想立即看到"新建了几个/跳过了几个"的执行结果反馈
  * 怀疑自动补种未生效时手动排查
用法：python manage.py seed_script_templates
"""
from django.core.management.base import BaseCommand
from apps.exec.seed_templates import seed_templates


class Command(BaseCommand):
    help = 'Seed a comprehensive library of monitoring script templates (Linux/Windows/MySQL/Oracle/MariaDB/Nginx/Tomcat/Apache/Redis/PostgreSQL/MongoDB/Docker)'

    def handle(self, *args, **options):
        created, skipped = seed_templates()
        if created == 0 and skipped == 0:
            self.stdout.write(self.style.WARNING(
                '未找到任何用户账号，跳过模板初始化。请先创建管理员账号后重新执行本命令。'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(f'脚本模板初始化完成：新建 {created} 个，已存在跳过 {skipped} 个'))
