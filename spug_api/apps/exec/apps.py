# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
from django.apps import AppConfig
from django.db.models.signals import post_migrate, post_save
import logging


def _auto_seed_templates(sender=None, **kwargs):
    """自动静默补种监控脚本模板库，确保无论首次安装、在线升级还是重装数据库，
    用户在「监控中心 → 自定义脚本 → 从模板添加」中都能看到开箱即用的模板，
    不依赖使用者记得额外手动执行一次命令。触发时机见下方 ready()。"""
    try:
        from apps.exec.seed_templates import seed_templates
        created, skipped = seed_templates()
        if created:
            logging.warning(f'[exec] 自动补种脚本模板：新建 {created} 个，已存在跳过 {skipped} 个')
    except Exception as e:
        # 不应因模板补种失败中断迁移/建号流程（例如相关表尚未就绪的边缘场景）
        logging.warning(f'[exec] 自动补种脚本模板跳过：{e}')


def _on_user_saved(sender, instance, created, **kwargs):
    """典型首次安装顺序是"先 migrate 建表，再创建管理员账号"，此时 post_migrate 触发时
    还没有任何用户，seed会被跳过；因此额外监听超级管理员账号创建，作为兜底触发点。"""
    if created and getattr(instance, 'is_supper', False):
        _auto_seed_templates()


class ExecConfig(AppConfig):
    name = 'apps.exec'
    verbose_name = '执行模板/批量执行'

    def ready(self):
        post_migrate.connect(_auto_seed_templates, sender=self)
        from apps.account.models import User
        post_save.connect(_on_user_saved, sender=User)
